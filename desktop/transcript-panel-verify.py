#!/usr/bin/env python3
"""Behavioral proof for the Mastermind room's decision #5: the slide-out
transcript panel — "the current session's text, with copy buttons,
clickable links, and code/commands easy to grab".

    python3 desktop/transcript-panel-verify.py

Same STUB + CDP pattern the other overnight-hardening verifiers on this box
already use (mic-hardening-verify.py, provider-failure-verify.py) — one
headless Chromium, one at a time, killed in a `finally`.

WHAT THIS DRIVES THROUGH THE REAL CODE PATH, NOT A SHORTCUT: the assistant
message is delivered via a real `claude:event` payload on
`window.__LISTENERS__['claude:event']`, exactly the shape `AppSink::event`
emits in the real app (see main.rs) — not a direct call into the transcript
store. That is the path that proves add('said', …), the actual conversation
render path, feeds Transcript.push() correctly, which is the thing most
likely to silently stop being true the next time either function is edited.

A SECOND, SEPARATE CHECK PROVES THE SECURITY PROPERTY, NOT JUST THE FEATURE:
a `javascript:` URI sitting in the assistant's own text must NOT become a
clickable link — see transcriptLinkify()'s own comment for why that gate
exists at all (model output is untrusted text).

WHO MAY RUN IT: anybody, locally. Contacts nothing outside this machine.
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
window.__COPIED__ = [];
try {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: async (t) => { window.__COPIED__.push(t); } },
    configurable: true,
  });
} catch (e) {}
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
  if (cmd === 'stop') return null;
  if (cmd === 'new_conversation') return null;
  if (cmd === 'send') return null;
  return null;
} }, event: { listen: async (name, cb) => {
  (window.__LISTENERS__[name] = window.__LISTENERS__[name] || []).push(cb);
  return () => {};
} } };
try { localStorage.setItem('nameos_onboarded_v1', '1'); } catch (e) {}
"""


def reveal(cdp):
    return cdp.js(
        "(() => { const g=document.getElementById('authGate'), "
        "a=document.getElementById('app'); if(g) g.hidden=true; if(a) a.hidden=false; "
        "return 'revealed'; })()")


ASSISTANT_TEXT = (
    "Sure — see https://example.com/docs for the reference, and here is the "
    "command:\n\n```bash\nnpm install --save-dev thing\n```\n\nAlso: "
    "javascript:alert(1) should stay plain text, not a link."
)


def main():
    port, dport = free_port(), free_port()
    serve(port)
    proc = subprocess.Popen(
        ["/snap/bin/chromium", "--headless=new", f"--remote-debugging-port={dport}",
         "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         "--use-fake-ui-for-media-stream",
         "--remote-allow-origins=*", "--window-size=1280,860",
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
               "try { closeSignin(); } catch(_) {} return true; })()")
        time.sleep(0.3)

        print("== 0. the door: hidden until pressed, matches the app's chrome ==")
        check("panel starts hidden", cdp.js("document.getElementById('transcriptPanel').hidden === true"))
        check("toggle button starts unpressed",
              cdp.js("document.getElementById('transcriptToggle').getAttribute('aria-pressed') === 'false'"))

        print("== 1. a real conversation, through add() exactly as production uses it ==")
        cdp.js("add('you', 'Can you help me set something up?'); true")
        cdp.js("window.__LISTENERS__['claude:event'][0]({ payload: { type:'assistant', "
               "message: { content: [ { type:'text', text: " + json.dumps(ASSISTANT_TEXT) + " } ] } } }); true")
        cdp.js("window.__LISTENERS__['claude:stderr'][0]({ payload: { text: 'a minor note' } }); true")
        time.sleep(0.1)
        check("three real entries landed in the store (you / said / err)",
              cdp.js("Transcript.entries.length") == 3, cdp.js("Transcript.entries.length"))
        check("'thinking' never enters the store — add('thinking', 'Working') "
              "from pending must not appear",
              cdp.js("Transcript.entries.every(e => e.kind !== 'thinking')"))

        print("== 2. open the panel via the toggle button ==")
        cdp.js("document.getElementById('transcriptToggle').click(); true")
        time.sleep(0.4)
        check("panel is no longer hidden", cdp.js("document.getElementById('transcriptPanel').hidden === false"))
        check("panel carries .open (actually slid in, not just unhidden)",
              cdp.js("document.getElementById('transcriptPanel').classList.contains('open')"))
        check("toggle button reflects pressed", cdp.js(
            "document.getElementById('transcriptToggle').getAttribute('aria-pressed') === 'true'"))
        check("three rows painted, one per entry",
              cdp.js("document.querySelectorAll('.transcriptEntry').length") == 3,
              cdp.js("document.querySelectorAll('.transcriptEntry').length"))
        shoot(cdp, "transcript-02-open.png")

        print("== 3. clickable links, the real requirement ==")
        check("the http(s) URL became a real <a href>",
              cdp.js("[...document.querySelectorAll('.transcriptText a')]"
                     ".some(a => a.href === 'https://example.com/docs')"))
        check("javascript: text stayed PLAIN TEXT, never an <a> -- the security gate",
              cdp.js("![...document.querySelectorAll('.transcriptText a')]"
                     ".some(a => a.getAttribute('href').startsWith('javascript'))"))
        check("the link opens in a new tab/window, not this one (target=_blank)",
              cdp.js("[...document.querySelectorAll('.transcriptText a')]"
                     ".every(a => a.target === '_blank' && a.rel.includes('noopener'))"))

        print("== 4. code/commands easy to grab, the other real requirement ==")
        check("a fenced code block became its own .transcriptCodeBlock",
              cdp.js("document.querySelectorAll('.transcriptCodeBlock').length") == 1)
        check("the code block's own text is exactly the command, nothing else",
              cdp.js("document.querySelector('.transcriptCodeBlock code').textContent.trim()")
              == "npm install --save-dev thing",
              cdp.js("document.querySelector('.transcriptCodeBlock code').textContent"))
        cdp.js("document.querySelector('.transcriptCodeBlock .transcriptCodeBar button').click(); true")
        time.sleep(0.1)
        check("clicking its Copy button copied ONLY the command, not the surrounding sentence",
              cdp.js("window.__COPIED__.includes('npm install --save-dev thing')"),
              cdp.js("window.__COPIED__"))
        shoot(cdp, "transcript-04-code-and-links.png")

        print("== 5. per-entry copy, and Copy the whole transcript ==")
        cdp.js("window.__COPIED__ = []; "
               "document.querySelector('.transcriptEntry.you .transcriptEntryCopy').click(); true")
        time.sleep(0.1)
        check("per-entry copy grabbed exactly that entry's text",
              cdp.js("window.__COPIED__.includes('Can you help me set something up?')"))
        cdp.js("window.__COPIED__ = []; "
               "document.getElementById('transcriptCopyAll').click(); true")
        time.sleep(0.1)
        whole = cdp.js("window.__COPIED__[0] || ''")
        check("Copy-all includes the user's line", "Can you help me set something up?" in whole)
        check("Copy-all includes the assistant's line", "example.com/docs" in whole)
        check("Copy-all includes the error line", "a minor note" in whole)

        print("== 6. the hotkey, Ctrl+Shift+T ==")
        cdp.send("Input.dispatchKeyEvent", type="keyDown", key="T", code="KeyT",
                  modifiers=10)  # ctrl(2)+shift(8)
        cdp.send("Input.dispatchKeyEvent", type="keyUp", key="T", code="KeyT", modifiers=10)
        time.sleep(0.4)
        check("Ctrl+Shift+T closed the (open) panel",
              cdp.js("!document.getElementById('transcriptPanel').classList.contains('open')"))
        cdp.send("Input.dispatchKeyEvent", type="keyDown", key="T", code="KeyT", modifiers=10)
        cdp.send("Input.dispatchKeyEvent", type="keyUp", key="T", code="KeyT", modifiers=10)
        time.sleep(0.4)
        check("Ctrl+Shift+T re-opened it",
              cdp.js("document.getElementById('transcriptPanel').classList.contains('open')"))

        print("== 7. Escape closes it without touching anything else ==")
        cdp.send("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape")
        cdp.send("Input.dispatchKeyEvent", type="keyUp", key="Escape", code="Escape")
        time.sleep(0.4)
        check("Escape closed the panel", cdp.js(
            "!document.getElementById('transcriptPanel').classList.contains('open')"))

        print("== 8. New chat clears the transcript along with the feed ==")
        cdp.js("document.getElementById('transcriptToggle').click(); true")
        time.sleep(0.4)
        cdp.js("document.getElementById('fresh').click(); true")
        time.sleep(0.2)
        check("Transcript.entries reset to just the 'New conversation.' note",
              cdp.js("Transcript.entries.length") == 1
              and cdp.js("Transcript.entries[0].text") == "New conversation.",
              cdp.js("JSON.stringify(Transcript.entries)"))
        check("the painted panel agrees (still open, live-repainted)",
              cdp.js("document.querySelectorAll('.transcriptEntry').length") == 1)
        shoot(cdp, "transcript-08-cleared-on-new-chat.png")

        print("== 9. the empty state reads as a state, not a blank box ==")
        cdp.js("Transcript.clear(); true")
        time.sleep(0.1)
        check("empty state message shown", cdp.js(
            "document.querySelector('.transcriptEmpty') !== null"))
        shoot(cdp, "transcript-09-empty.png")

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
