#!/usr/bin/env python3
"""Behavioral proof for overnight hardening batch #2 (device-change recovery,
the mic-state indicator, hard mute + push-to-talk).

Same STUB + CDP pattern wren-composer-gate-shots.py already proved out on
this box (one Chromium, one at a time, `--disable-gpu --no-sandbox`, killed
in a `finally`) -- reused rather than reinvented. What's new here is a MOCK
SpeechRecognition, injected the same way the __TAURI__ stub is (via
Page.addScriptToEvaluateOnNewDocument, so it exists before index.html's own
`const SpeechRecognitionCtor = window.SpeechRecognition || ...` line ever
runs) -- there is no real speech engine to test against in this headless,
audio-less sandbox (see FACTS.md: no node speech stack here, and this app's
own Linux webview has none either), so the mock is what lets onstart/
onresult/onerror/onend be driven directly and their effects on the mic
button, the pill, and the voice bar be read back from the real DOM.

Two things this proves for real rather than by mock, because the sandbox
actually has them: `navigator.mediaDevices.enumerateDevices()` genuinely
returns zero audioinput devices (no fake mic exists here), and
`getUserMedia()` genuinely rejects for the same reason -- so the
"unavailable" and self-test-failure paths are exercised against real
browser behaviour, not simulated.

WHAT THIS DOES NOT PROVE: whether WebView2 on the real Windows box fires
these same SpeechRecognition error codes and devicechange events the same
way Chromium does. That is the same disclosure mic_hotkeys.rs's own header
carries for the global hotkeys -- Beck's to confirm on the real box.

    python3 desktop/mic-hardening-verify.py

Contacts nothing outside this machine.
"""
import base64
import http.server
import json
import pathlib
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE / "ui"
OUT = pathlib.Path.home() / "snap" / "firefox" / "common"  # harmless if unused; chromium writes fine to $HOME too
OUT = pathlib.Path.home()

FAILS = []


def check(label, cond, detail=""):
    mark = "OK " if cond else "FAIL"
    print(f"  [{mark}] {label}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(label + (f" ({detail})" if detail else ""))


def free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def serve(port):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(UI), **k)

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


class CDP:
    def __init__(self, port):
        self.port, self.n, self.ws = port, 0, None

    def connect(self):
        import websocket
        for _ in range(60):
            try:
                tabs = json.loads(urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json").read())
                pages = [t for t in tabs if t["type"] == "page"]
                if pages:
                    self.ws = websocket.create_connection(
                        pages[0]["webSocketDebuggerUrl"], timeout=40)
                    return
            except Exception:
                time.sleep(0.5)
        raise SystemExit("could not attach to Chromium over CDP")

    def send(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise SystemExit(f"{method}: {m['error']}")
                return m.get("result", {})

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr,
                       awaitPromise=True, returnByValue=True)
        if r.get("exceptionDetails"):
            raise SystemExit(f"JS threw: {r['exceptionDetails']}")
        return r.get("result", {}).get("value")

    def resize(self, w, h):
        self.send("Emulation.setDeviceMetricsOverride", width=w, height=h,
                   deviceScaleFactor=1, mobile=False)


def shoot(cdp, name):
    png = cdp.send("Page.captureScreenshot", format="png")["data"]
    p = OUT / name
    p.write_bytes(base64.b64decode(png))
    print(f"  shot: {p}")
    return p


STUB = r"""
window.__STATE__ = { ready:true, problem:null, path:'/usr/bin/claude',
  version:'2.1.250', detail:null, logged_in:true };
window.__PROV__ = { providers: [ { id:'claude', kind:'claude', name:'Claude',
  base_url:'', model:'', builtin:true, connected:true, disconnected:false,
  checked_at:'', last_error:'', has_secret:false, caveat:'', migration_note:'' }
], active: 'claude' };
window.__LISTENERS__ = {};
window.__TAURI__ = { core: { invoke: async (cmd, args) => {
  if (cmd === 'default_workdir') return '/home/you/Documents/NameOS';
  if (cmd === 'is_folder') return true;
  if (cmd === 'preflight') return window.__STATE__;
  if (cmd === 'load_profile') return { about:'', goal:'', memory:'',
    assistantName:'Bella', personality:'', wakeWord:'' };
  if (cmd === 'list_providers') return window.__PROV__;
  if (cmd === 'list_connectors') return [];
  if (cmd === 'list_live_servers') return [];
  if (cmd === 'recommended_ai') return { cloud: [], local: [] };
  if (cmd === 'detect_local_brain') return { running:false, models:[], problem:'' };
  if (cmd === 'check_update') return { available:false, currentVersion:'0.2.0' };
  if (cmd === 'is_running') return false;
  if (cmd === 'list_skills') return [];
  if (cmd === 'list_facts') return [];
  if (cmd === 'memory_stats') return { total:0, assistantCount:0, verifiedCount:0 };
  if (cmd === 'scan_notes') return { nodes: [], edges: [], truncated: false };
  if (cmd === 'sync_profile') return null;
  if (cmd === 'run') return null;
  if (cmd === 'stop') return null;
  if (cmd === 'new_conversation') return null;
  return null;
} }, event: { listen: async (name, cb) => {
  (window.__LISTENERS__[name] = window.__LISTENERS__[name] || []).push(cb);
  return () => {};
} } };
try { localStorage.setItem('nameos_onboarded_v1', '1'); } catch (e) {}

// --- Mock SpeechRecognition ---------------------------------------------
// Installed BEFORE index.html's own script reads window.SpeechRecognition /
// webkitSpeechRecognition, so the app's real startWake()/beginRecognition()
// code path runs unmodified against this instead of a real engine.
class MockRecognition {
  constructor() {
    this.continuous = false; this.interimResults = false; this.lang = '';
    this.onstart = null; this.onresult = null; this.onerror = null; this.onend = null;
    MockRecognition.instances.push(this);
  }
  start() { MockRecognition.startCount++; setTimeout(() => { this.onstart && this.onstart(); }, 0); }
  stop() { setTimeout(() => { this.onend && this.onend(); }, 0); }
  abort() { MockRecognition.abortCount++; setTimeout(() => { this.onend && this.onend(); }, 0); }
  fireResult(transcript, isFinal, resultIndex) {
    if (!this.onresult) return;
    const item = Object.assign([{ transcript }], { isFinal: !!isFinal });
    this.onresult({ resultIndex: resultIndex || 0, results: [item] });
  }
  fireError(error) {
    // A REAL SpeechRecognitionErrorEvent IS FOLLOWED BY 'end' -- per the Web
    // Speech API's own processing model (an error terminates the session),
    // which the app's onend handler depends on to run its restart/give-up
    // logic at all. Without this the mock would leave the app's `listening`
    // flag stuck true forever after an error, which no real engine does.
    this.onerror && this.onerror({ error });
    setTimeout(() => { this.onend && this.onend(); }, 0);
  }
}
MockRecognition.instances = [];
MockRecognition.startCount = 0;
MockRecognition.abortCount = 0;
window.SpeechRecognition = MockRecognition;
window.__MockRecognition__ = MockRecognition;
"""


def reveal(cdp):
    return cdp.js(
        "(() => { const g=document.getElementById('authGate'), "
        "a=document.getElementById('app'); if(g) g.hidden=true; if(a) a.hidden=false; "
        "return 'revealed'; })()")


def main():
    port, dport = free_port(), free_port()
    serve(port)
    proc = subprocess.Popen(
        ["/snap/bin/chromium", "--headless=new", f"--remote-debugging-port={dport}",
         "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         "--use-fake-ui-for-media-stream",
         "--remote-allow-origins=*", "--window-size=1280,800",
         f"http://127.0.0.1:{port}/index.html"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        cdp = CDP(dport)
        cdp.connect()
        cdp.send("Runtime.enable")
        cdp.send("Page.enable")
        cdp.send("Page.addScriptToEvaluateOnNewDocument", source=STUB)
        cdp.send("Page.reload")
        time.sleep(2.2)
        reveal(cdp)
        cdp.js("(async () => { await loadProviders(); await check(); "
               "try { closeSignin(); } catch(_) {} "
               "askWake.value=''; askName.value='Bella'; return refreshWake(); })()")
        time.sleep(0.3)

        print("== 0. baseline ==")
        check("SpeechRecognitionCtor resolved to the mock",
              cdp.js("typeof SpeechRecognitionCtor === 'function' && SpeechRecognitionCtor === window.__MockRecognition__"))
        check("mic_hotkeys listeners registered: mic:mute-toggle",
              cdp.js("Array.isArray(window.__LISTENERS__['mic:mute-toggle']) && window.__LISTENERS__['mic:mute-toggle'].length > 0"))
        check("mic_hotkeys listeners registered: mic:ptt",
              cdp.js("Array.isArray(window.__LISTENERS__['mic:ptt']) && window.__LISTENERS__['mic:ptt'].length > 0"))
        check("wake NOT armed by default on a fresh profile (PTT is now the "
              "out-of-box default, Mark's room, 2026-09-04)",
              cdp.js("wakeArmed === false"))
        check("VOICE_WAKE_KEY is genuinely absent, not a stored '0' — this is "
              "'never chosen', not 'chosen off'",
              cdp.js("localStorage.getItem('nameos_wake_listening') === null"))
        shoot(cdp, "mic-00-baseline-ptt-default.png")

        print("== 0b. an install that already opted into always-listening keeps it ==")
        # Same profile, same reveal — only the stored preference differs. This
        # is armMicIfWanted()'s own explicit-opt-in test, exercised the same
        # way an app boot would: set the key BEFORE the function runs, not
        # after, so this proves the read path rather than just setting
        # wakeArmed by hand and declaring victory.
        cdp.js("localStorage.setItem('nameos_wake_listening', '1'); "
               "wakeArmed = false; armMicIfWanted(); true")
        time.sleep(0.1)
        check("an explicit '1' still auto-arms on boot — an existing user who "
              "turned this on (even under the old default) is unaffected",
              cdp.js("wakeArmed === true"))
        shoot(cdp, "mic-00b-existing-user-preserved.png")

        print("== 1. hard mute, via the same event Rust would send ==")
        # Continuing from 0b with wake-word genuinely armed and a live mock
        # session running — mute/device-recovery below are testing the
        # always-listening MACHINERY, not the default, so they need a session
        # to actually mute/recover regardless of what a fresh install starts
        # with.
        cdp.js("window.__LISTENERS__['mic:mute-toggle'][0]()")
        time.sleep(0.05)
        check("hardMuted is true", cdp.js("hardMuted === true"))
        check("mic button carries .muted", cdp.js("document.getElementById('mic').classList.contains('muted')"))
        check("mic button does NOT carry .listening while muted",
              cdp.js("!document.getElementById('mic').classList.contains('listening')"))
        check("pill reads muted", cdp.js("document.getElementById('voicePill').classList.contains('muted')"))
        check("voice bar shows the muted banner",
              cdp.js("document.getElementById('voiceBar').hidden === false && "
                     "document.getElementById('voiceBar').textContent.includes('muted')"))
        check("recognition was actually aborted, not just flagged",
              cdp.js("window.__MockRecognition__.abortCount > 0"))
        check("wakeArmed left untouched by the mute (per its own design comment)",
              cdp.js("wakeArmed === true"))
        shoot(cdp, "mic-01-muted.png")

        print("== 2. beginRecognition() refuses to start a new session while muted ==")
        before = cdp.js("window.__MockRecognition__.startCount")
        cdp.js("beginRecognition(); true")
        after = cdp.js("window.__MockRecognition__.startCount")
        check("no new session was started", after == before, f"before={before} after={after}")

        print("== 3. unmute via the mic button click (mouse-only path, no hotkey) ==")
        cdp.js("document.getElementById('mic').click(); true")
        time.sleep(0.1)
        check("hardMuted is false again", cdp.js("hardMuted === false"))
        check("mic button lost .muted", cdp.js("!document.getElementById('mic').classList.contains('muted')"))
        check("the muted banner is gone (armMicIfWanted repainted)",
              cdp.js("!document.getElementById('voiceBar').classList.contains('bad')"))
        check("a fresh recognition session was started", cdp.js("window.__MockRecognition__.startCount > 0"))
        shoot(cdp, "mic-03-unmuted.png")

        print("== 4. push-to-talk: held speech needs no wake word ==")
        cdp.js("window.__LISTENERS__['mic:ptt'][0]({ payload: { pressed: true } })")
        time.sleep(0.05)
        check("pttActive is true", cdp.js("pttActive === true"))
        check("anchor window pinned open (Infinity)", cdp.js("anchorUntil === Infinity"))
        before_you = cdp.js("feed.querySelectorAll('.you').length")
        cdp.js("(window.__MockRecognition__.instances.at(-1)).fireResult('what time is it', true); true")
        time.sleep(0.05)
        after_you = cdp.js("feed.querySelectorAll('.you').length")
        check("a bare sentence with NO wake word was submitted while PTT held",
              after_you == before_you + 1, f"before={before_you} after={after_you}")
        last_text = cdp.js("feed.querySelectorAll('.you')[feed.querySelectorAll('.you').length-1].textContent")
        check("the submitted text is exactly what was heard (not wake-word-stripped)",
              "what time is it" in (last_text or ""), repr(last_text))

        # Release the button from step 4 -- otherwise pttStart()'s own
        # re-entrancy guard (`if (pttActive) return;`) makes every check below
        # a false pass for the wrong reason. FAST-FORWARDED the same way step
        # 5 does below: a real, un-captured PTT_TAIL_MS (1200ms) timer left
        # ticking here fires naturally in the MIDDLE of steps 5-7 and was
        # caught mutating state out from under them (an extra, unexplained
        # abort() a couple of steps later) -- every background timer this
        # test can trigger has to be resolved before moving on, not just the
        # one each step is actually about.
        cdp.js("""
          window.__origSetTimeout = window.setTimeout;
          window.__capturedTimer = null;
          window.setTimeout = (fn, ms) => { window.__capturedTimer = fn; return window.__origSetTimeout(fn, 60000); };
          window.__LISTENERS__['mic:ptt'][0]({ payload: { pressed: false } });
          true
        """)
        cdp.js("if (window.__capturedTimer) window.__capturedTimer(); "
               "window.setTimeout = window.__origSetTimeout; true")
        time.sleep(0.05)

        print("== 5. push-to-talk release: engine stops if wake word was never armed ==")
        cdp.js("stopWake(); true")  # simulate "push-to-talk only" mode: wake word off
        time.sleep(0.05)
        check("wake word is now off (PTT-only mode)", cdp.js("wakeArmed === false"))
        cdp.js("window.__LISTENERS__['mic:ptt'][0]({ payload: { pressed: true } }); true")
        time.sleep(0.05)
        check("PTT still starts a session even with wake word off",
              cdp.js("pttActive === true && listening === true"))
        # Fast-forward the PTT tail without a real 1200ms sleep: capture the
        # timer setTimeout() actually scheduled and invoke it directly.
        cdp.js("""
          window.__origSetTimeout = window.setTimeout;
          window.__capturedTimer = null;
          window.setTimeout = (fn, ms) => { window.__capturedTimer = fn; return window.__origSetTimeout(fn, 60000); };
          true
        """)
        cdp.js("window.__LISTENERS__['mic:ptt'][0]({ payload: { pressed: false } }); true")
        time.sleep(0.05)
        check("pttActive false immediately on release", cdp.js("pttActive === false"))
        cdp.js("if (window.__capturedTimer) window.__capturedTimer(); "
               "window.setTimeout = window.__origSetTimeout; true")
        time.sleep(0.05)
        check("engine stopped after the tail window (wake word was never armed)",
              cdp.js("listening === false"))
        shoot(cdp, "mic-05-ptt-released.png")

        print("== 6. device vanishes mid-session: recognition.onerror('audio-capture') ==")
        cdp.js("startWake(); true")
        time.sleep(0.05)
        check("a session is running again", cdp.js("listening === true"))
        cdp.js("(window.__MockRecognition__.instances.at(-1)).fireError('audio-capture'); true")
        time.sleep(0.05)
        check("micUnavailable set immediately, not after 3 silent retries",
              cdp.js("micUnavailable === true"))
        check("mic button carries .unavailable", cdp.js("document.getElementById('mic').classList.contains('unavailable')"))
        check("voice bar says a device is missing",
              cdp.js("document.getElementById('voiceBar').textContent.includes('No microphone found')"))
        shoot(cdp, "mic-06-unavailable.png")

        print("== 7. devicechange event (real EventTarget dispatch): recovers once a device is claimed ==")
        cdp.js("navigator.mediaDevices.enumerateDevices = async () => "
               "[{ kind: 'audioinput', deviceId: 'fake', label: 'Fake Mic' }]; true")
        cdp.js("navigator.mediaDevices.dispatchEvent(new Event('devicechange')); true")
        time.sleep(0.7)  # the 400ms debounce plus a margin
        check("micUnavailable cleared on its own once a device reappeared",
              cdp.js("micUnavailable === false"))
        check("the unavailable banner cleared with it",
              cdp.js("!document.getElementById('voiceBar').classList.contains('bad')"))
        debug = cdp.js("JSON.stringify({listening, wakeArmed, pttActive, hardMuted, "
                       "micFastFailStreak, micGaveUp, startCount: window.__MockRecognition__.startCount, "
                       "abortCount: window.__MockRecognition__.abortCount})")
        print("    debug:", debug)
        check("recognition restarted without the mic button being touched",
              cdp.js("listening === true"))
        shoot(cdp, "mic-07-recovered.png")

        print("== 8. the give-up recovery path (micGaveUp), independent of #6/#7 ==")
        cdp.js("recognition && recognition.abort(); wakeArmed = false; micGaveUp = true; "
               "micUnavailable = false; localStorage.setItem('nameos_wake_listening','1'); true")
        cdp.js("navigator.mediaDevices.dispatchEvent(new Event('devicechange')); true")
        time.sleep(0.6)
        check("micGaveUp recovery re-armed the wake word on its own",
              cdp.js("wakeArmed === true && micGaveUp === false"))
        shoot(cdp, "mic-08-gaveup-recovered.png")

        print("== 9. no audio input at all: enumerateDevices genuinely empty in this sandbox ==")
        cdp.js("navigator.mediaDevices.enumerateDevices = async () => []; true")
        cdp.js("recoverFromDeviceChange(); true")
        time.sleep(0.3)
        check("micUnavailable true against a real (stubbed-empty) enumeration",
              cdp.js("micUnavailable === true"))

        print("== 10. the self-test button, against this sandbox's REAL lack of a microphone ==")
        cdp.js("navigator.mediaDevices.enumerateDevices = async () => []; hardMuted = false; "
               "micUnavailable = false; document.getElementById('mic').classList.remove('unavailable','muted'); true")
        # THE REAL OPEN PATH, not just un-hiding the pane -- openAbout('me')
        # is what a person actually triggers (About me -> the wake-word
        # field's own "Test microphone" button), so this is what proves the
        # button lives somewhere reachable, not just present in the DOM.
        cdp.js("openAbout('me'); true")
        time.sleep(0.3)
        check("the About-me sheet is actually open",
              cdp.js("!document.getElementById('aboutSheet').hidden"))
        shoot(cdp, "mic-10a-selftest-panel-closed.png")
        cdp.js("document.getElementById('micTest').click(); true")
        time.sleep(1.0)
        status = cdp.js("document.getElementById('micTestStatus').textContent")
        check("self-test reports it could not open a (genuinely absent) microphone",
              "Could not open" in (status or ""), repr(status))
        # micTestStream WAS the module-level flag proving this; helloim.ai
        # onboarding, 2026-09-04 turned the self-test into createMicTest(), a
        # factory with its own instance-local `stream` -- Profile's own panel
        # and the first-run wizard's "Mic check" step can each have one open.
        # activeMicTests is the one thing still SHARED (so a hard mute can
        # reach every open self-test at once, see setHardMuted()'s own
        # comment) -- checking it empty is the equivalent proof in the new
        # shape: nothing anywhere still holds a live capture.
        check("no stream was left behind", cdp.js("activeMicTests.size === 0"))
        shoot(cdp, "mic-10b-selftest-no-device.png")

        print("== 11. the About-me opt-in checkbox — the actual settings control ==")
        # wakeArmed is true here, carried over from #8's recovery — so the
        # checkbox opening CHECKED is itself a check: it has to read the
        # real armMicIfWanted()/startWake() state, not a value cached at
        # some earlier paint.
        check("checkbox reflects wake-word already being on",
              cdp.js("document.getElementById('askWakeAlways').checked === true"))
        # NOT `const b = ...` -- Runtime.evaluate calls share one persistent
        # global scope across this whole script, and a second `const` with
        # the same name a few lines below throws SyntaxError: Identifier 'b'
        # has already been declared. Re-query the element each time instead.
        cdp.js("document.getElementById('askWakeAlways').checked = false; "
               "document.getElementById('askWakeAlways').dispatchEvent(new Event('change')); true")
        time.sleep(0.1)
        check("unticking the box actually calls stopWake()",
              cdp.js("wakeArmed === false"))
        check("and the preference on disk agrees",
              cdp.js("localStorage.getItem('nameos_wake_listening') === '0'"))
        shoot(cdp, "mic-11a-checkbox-off.png")
        startCountBefore = cdp.js("window.__MockRecognition__.startCount")
        cdp.js("document.getElementById('askWakeAlways').checked = true; "
               "document.getElementById('askWakeAlways').dispatchEvent(new Event('change')); true")
        time.sleep(0.1)
        check("reticking the box actually calls startWake()",
              cdp.js("wakeArmed === true"))
        check("and the preference on disk agrees",
              cdp.js("localStorage.getItem('nameos_wake_listening') === '1'"))
        check("a real recognition session was started, not just the flag flipped",
              cdp.js("window.__MockRecognition__.startCount") > startCountBefore)
        shoot(cdp, "mic-11b-checkbox-on.png")

        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    code = main()
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILED:")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    print("All checks passed.")
    sys.exit(code)
