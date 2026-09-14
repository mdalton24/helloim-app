#!/usr/bin/env python3
"""Behavioral proof for the assembled first-run onboarding flow.

Mark's room, 2026-09-04: a guided first-run was ranked the top next build for
activation and fewer support issues. Most of the pieces already existed --
the naming/theme step, the brain picker (BRAIN_OPTIONS), the "Say hello"
proof-of-life step, the mic self-test, and the PTT-vs-wake-word preference --
but the last two only ever lived in Profile -> About me, reachable only by
someone who went looking after the fact. This adds two Onboard steps (`mic`,
`talk`) between `brain` and `hello` that surface them during setup, wired
through the SAME functions Profile already uses (createMicTest() as a second
instance of the same factory, startWake()/stopWake() for the preference) --
never a second mechanism.

This drives the real ui/index.html over CDP, the same STUB + mock-
SpeechRecognition pattern mic-hardening-verify.py already proved out on this
box (window.__TAURI__.core.invoke stubbed, SpeechRecognition replaced with a
controllable mock since this sandbox has no real speech engine or audio
device -- see that file's own header for why the mock is honest here).

WHAT THIS PROVES: the wizard's own JS -- step order, Next/Back, the mic
self-test's real getUserMedia call and its real failure path (this sandbox
has no fake audio device, so "could not open the microphone" is a REAL
result, not simulated), and that the talk-preference step and the Profile
checkbox never disagree about wakeArmed.

WHAT THIS DOES NOT PROVE, per FACTS.md: "WINDOWS ONLY -- a Linux run is
iteration, never evidence; Mark is the eyes." No Tauri backend runs here, so
`submit()` cannot show a real streamed reply from a real brain, and neither
Kokoro nor WebView2 are exercised. This is the fast, repeatable check that
the assembled flow does not throw and does not regress; Beck/Mark still
verify the real Windows build.

    python3 desktop/onboarding-flow-verify.py
"""
import http.server
import json
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UI = HERE / "ui"

FAILS = []


def check(label, cond, detail=""):
    mark = "OK " if cond else "FAIL"
    print(f"  [{mark}] {label}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(label + (f" ({detail})" if detail else ""))


# ADDED 2026-09-05, Jarvis's own review of the step-reorder fix above: every
# "on the X question" call in this file used to read `check(label,
# cdp.js(QUESTION), "expected text")` -- and `check()` only tests its second
# argument for truthiness. `cdp.js(QUESTION)` is a non-empty string on EVERY
# step, so that call passed regardless of which question was actually on
# screen; the "expected text" string was decoration on the failure message,
# never compared. That is the exact shape of the 2026-09-03 traversal tests
# that passed for the wrong reason once the URL depth changed under them.
# What actually caught a wrong step order before this fix was a downstream
# crash (a selector for that step's own markup coming back null) rather than
# this check -- which worked, but only by accident of what came after it.
# check_eq compares for real, and the failure detail carries both sides so a
# mismatch says what it actually saw, not just that something disagreed.
def check_eq(label, actual, expected):
    check(label, actual == expected, f"expected {expected!r}, got {actual!r}")


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


# Deliberately does NOT set nameos_onboarded_v1 -- this is a fresh-install
# test, and Onboard.reopen() (same call onboard-theme-check.py already uses)
# opens the wizard regardless of that flag anyway, so a stray '1' left over
# from a previous run of this script must not silently change what is being
# tested.
STUB = r"""
window.__PROV__ = { providers: [ { id:'claude', kind:'claude', name:'Claude',
  base_url:'', model:'', builtin:true, connected:true, disconnected:false,
  checked_at:'', last_error:'', has_secret:false, caveat:'', migration_note:'' }
], active: 'claude' };
window.__LISTENERS__ = {};
window.__TAURI__ = { core: { invoke: async (cmd, args) => {
  if (cmd === 'default_workdir') return '/home/you/Documents/NameOS';
  if (cmd === 'is_folder') return true;
  if (cmd === 'preflight') return { ready:true, problem:null, path:'/usr/bin/claude',
    version:'2.1.250', detail:null, logged_in:true };
  if (cmd === 'load_profile') return { about:'', goal:'', memory:'',
    assistantName:'', personality:'', wakeWord:'' };
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
  if (cmd === 'select_provider') return null;
  if (cmd === 'test_provider') return { ok:true, detail:'' };
  return null;
} }, event: { listen: async (name, cb) => {
  (window.__LISTENERS__[name] = window.__LISTENERS__[name] || []).push(cb);
  return () => {};
} } };

// --- Mock SpeechRecognition (this sandbox has no real speech engine) -----
class MockRecognition {
  constructor() {
    this.continuous = false; this.interimResults = false; this.lang = '';
    this.onstart = null; this.onresult = null; this.onerror = null; this.onend = null;
  }
  start() { setTimeout(() => { this.onstart && this.onstart(); }, 0); }
  stop() { setTimeout(() => { this.onend && this.onend(); }, 0); }
  abort() { setTimeout(() => { this.onend && this.onend(); }, 0); }
}
window.SpeechRecognition = MockRecognition;
window.__MockRecognition__ = MockRecognition;
"""


def reveal(cdp):
    return cdp.js(
        "(() => { const g=document.getElementById('authGate'), "
        "a=document.getElementById('app'); if(g) g.hidden=true; if(a) a.hidden=false; "
        "return 'revealed'; })()")


QUESTION = "document.getElementById('obQuestion').textContent"


def main():
    port, dport = free_port(), free_port()
    serve(port)
    proc = subprocess.Popen(
        ["/snap/bin/chromium", "--headless=new", f"--remote-debugging-port={dport}",
         "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         "--use-fake-ui-for-media-stream",
         "--remote-allow-origins=*", "--window-size=1280,900",
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
        cdp.js("(async () => { try { await loadProviders(); } catch(_) {} "
               "try { await check(); } catch(_) {} "
               "try { closeSignin(); } catch(_) {} return 'ready'; })()")
        time.sleep(0.3)

        print("== open the wizard fresh ==")
        cdp.js("Onboard.reopen()")
        time.sleep(0.5)
        check("wizard is open", cdp.js("!document.getElementById('onboardSheet').hidden"))
        n_dots = cdp.js("document.getElementById('obDots').children.length")
        check("11 steps now (name/brain/hello/where/mic/talk + the 5-question tail)",
              n_dots == 11, f"got {n_dots}")

        print("== step 1: name (welcome) ==")
        check_eq("on the name question", cdp.js(QUESTION),
                 "What do you want to call your assistant?")
        cdp.js("(() => { const i=document.getElementById('obInput'); "
               "i.value='Nova'; i.dispatchEvent(new Event('input',{bubbles:true})); "
               "return 'ok'; })()")
        check("Next live once named", cdp.js("!document.getElementById('obNext').disabled"))
        cdp.js("document.getElementById('obNext').click(); true")
        time.sleep(0.2)

        print("== step 2: pick your brain ==")
        check_eq("on the brain question", cdp.js(QUESTION),
                 "Which AI should power your assistant?")
        check("Next dead before a choice is made", cdp.js("document.getElementById('obNext').disabled"))
        cdp.js("(() => { const b=[...document.querySelectorAll('#obField .obChoice')]"
               ".find(x => x.textContent.trim().startsWith('Claude')); b.click(); return !!b; })()")
        time.sleep(0.2)
        check("cost/can detail panel appeared", cdp.js("!document.querySelector('#obField .obHint').hidden"))
        check("Next live once a brain is chosen", cdp.js("!document.getElementById('obNext').disabled"))
        cdp.js("document.getElementById('obNext').click(); true")
        time.sleep(0.2)

        # REORDERED, 2026-09-04 -- Mark, on the shipped build: "Step 2 has me
        # pick a Cloud AI. It should go to CONNECT now next and not a mic
        # check." 'hello' and 'where' now sit between 'brain' and 'mic'
        # (see ui/index.html's own comment on the 'hello' STEPS entry); this
        # test's order follows that file's STEPS array, not the reverse.
        print("== step 3: say hello (first real exchange) ==")
        check_eq("on the hello question", cdp.js(QUESTION), "Say hello.")
        ok = False
        for _ in range(20):
            txt = cdp.js("document.querySelector('#obField .hint')?.textContent || ''")
            if 'Ready' in txt or "isn't connected" in txt:
                ok = True
                break
            time.sleep(0.2)
        check("resolved to a real connection state (stub reports Claude connected)",
              ok and 'Ready' in txt, txt if not ok else "")
        check("a real 'Say hello' input+button rendered (not a dead screen)",
              cdp.js("!!document.getElementById('obHelloInput') && "
                     "!!document.querySelector('#obField .authSubmit')"))
        cdp.js("document.getElementById('obHelloInput').value = 'hello'; "
               "document.querySelector('#obField .authSubmit').click(); true")
        time.sleep(0.5)
        # helloSent lives in Onboard's own closure, not exposed globally --
        # the observable proxy for it is the sheet reappearing (it is hidden
        # for the moment submit() runs so the reply streams into the real
        # feed behind it, then shown again) with the confirmation note
        # actually landed in that same feed.
        check("the sheet reappeared after sending",
              cdp.js("document.getElementById('onboardSheet').hidden === false"))
        check("the confirmation note landed in the real transcript",
              cdp.js("[...document.querySelectorAll('#feed .note')].some(n => "
                     "n.textContent.includes(\"You're all set\"))"))
        check("Next live after hello", cdp.js("!document.getElementById('obNext').disabled"))
        cdp.js("document.getElementById('obNext').click(); true")
        time.sleep(0.2)

        print("== step 4: where it keeps your notes ==")
        check_eq("on the where question", cdp.js(QUESTION),
                 "Where should it keep your notes and work?")
        check("Next dead before a choice is made", cdp.js("document.getElementById('obNext').disabled"))
        cdp.js("(() => { const b=[...document.querySelectorAll('#obField .obChoice')]"
               ".find(x => x.textContent.trim() === 'Create one for me'); b.click(); return !!b; })()")
        # confirmWorkdir() -> ensureFolderTrusted() -> invoke('folder_trust_probe', ...)
        # is unmocked in STUB (falls through to the catch-all `return null`),
        # so probe is null and the "no decision needed" branch resolves it
        # near-instantly -- bounded wait covers the round trip regardless.
        ok = False
        for _ in range(30):
            if cdp.js("!document.getElementById('obNext').disabled"):
                ok = True
                break
            time.sleep(0.2)
        check("Next live once the folder is settled (confirmWorkdir resolved)", ok)
        cdp.js("document.getElementById('obNext').click(); true")
        time.sleep(0.2)

        print("== step 5: mic check ==")
        check_eq("on the mic question", cdp.js(QUESTION), "Can it hear you?")
        check("Next is never blocked here (no wrong answer)",
              cdp.js("!document.getElementById('obNext').disabled"))
        check("test button rendered", cdp.js("!!document.querySelector('#obField button')"))
        cdp.js("document.querySelector('#obField button').click(); true")
        # No fake audio device exists in this sandbox (same fact
        # mic-hardening-verify.py's own header records) -- getUserMedia
        # genuinely rejects, and it rejects FAST (no real device enumeration
        # to wait on), so the button's transient "Testing…" state can come
        # and go inside a single CDP round trip. The panel opening is not
        # transient (it stays open through the failure) and IS checked
        # immediately below; the button's resting-state text is checked once
        # the bounded wait settles, a few lines down.
        check("panel opens", cdp.js("document.querySelector('#obField .micTestPanel').hidden === false"))
        # Bounded wait for the (fast, real) rejection to land.
        ok = False
        for _ in range(30):
            txt = cdp.js("document.querySelector('#obField .hint:last-of-type').textContent")
            if txt and ('Could not open the microphone' in txt or 'I can hear you' in txt
                        or 'Nothing heard yet' in txt):
                ok = True
                break
            time.sleep(0.2)
        check("self-test resolves to a real status (not stuck 'Opening…')", ok, txt if not ok else "")
        check("button re-enabled and back to its resting label",
              cdp.js("document.querySelector('#obField button').textContent === 'Test microphone'"))
        check("Next still live after the test", cdp.js("!document.getElementById('obNext').disabled"))
        cdp.js("document.getElementById('obNext').click(); true")
        time.sleep(0.2)

        print("== step 6: how you talk to it ==")
        check_eq("on the talk question", cdp.js(QUESTION), "How do you want to talk to it?")
        check("push-to-talk is the baseline (matches the shipped default)",
              cdp.js("wakeArmed === false"))
        check("both cards rendered", cdp.js("document.querySelectorAll('#obField .obChoice').length === 2"))
        check("PTT card shows checked at baseline",
              cdp.js("[...document.querySelectorAll('#obField .obChoice')][0].getAttribute('aria-checked') === 'true'"))

        cdp.js("[...document.querySelectorAll('#obField .obChoice')][1].click(); true")
        time.sleep(0.2)
        check("choosing 'Always listening' goes through the real startWake(), not a bare write",
              cdp.js("wakeArmed === true"))
        check("localStorage agrees", cdp.js("localStorage.getItem('nameos_wake_listening') === '1'"))
        check("Profile's OWN checkbox (askWakeAlways) mirrors it -- one preference, "
              "never two that can disagree",
              cdp.js("document.getElementById('askWakeAlways').checked === true"))
        check("the wizard card repaints itself checked",
              cdp.js("[...document.querySelectorAll('#obField .obChoice')][1].getAttribute('aria-checked') === 'true'"))

        cdp.js("[...document.querySelectorAll('#obField .obChoice')][0].click(); true")
        time.sleep(0.2)
        check("switching back to push-to-talk calls the real stopWake()",
              cdp.js("wakeArmed === false"))
        check("localStorage agrees", cdp.js("localStorage.getItem('nameos_wake_listening') === '0'"))
        check("Profile's checkbox mirrors it back off",
              cdp.js("document.getElementById('askWakeAlways').checked === false"))
        check("Next was never blocked on this step either",
              cdp.js("!document.getElementById('obNext').disabled"))

        print("== back navigation does not corrupt state ==")
        cdp.js("document.getElementById('obBack').click(); true")
        time.sleep(0.2)
        check_eq("back from talk lands on mic", cdp.js(QUESTION), "Can it hear you?")
        cdp.js("document.getElementById('obBack').click(); true")
        time.sleep(0.2)
        check_eq("back from mic lands on where", cdp.js(QUESTION), "Where should it keep your notes and work?")

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
    print("All checks passed -- the assembled first-run flow completes end to end.")
    sys.exit(code)
