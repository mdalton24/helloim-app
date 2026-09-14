#!/usr/bin/env python3
"""Behavioral proof for the Mastermind room's decision #2: a provider that
fails, mid-chat or on dispatch, STOPS and lets the person choose — it is
never silently retried against a different brain.

    python3 desktop/provider-failure-verify.py

Same STUB + CDP pattern mic-hardening-verify.py and wren-local-gates-shots.py
already proved out on this box (one Chromium, one at a time, headless,
`--disable-gpu --no-sandbox`, killed in a `finally`) — reused rather than
reinvented.

WHAT THIS PROVES, AND WHY IT NEEDS TWO SHAPES, NOT ONE. A "provider failure"
in this app is two genuinely different code paths, and a fix (or a
regression) in one says nothing about the other:

  1. `invoke('send', ...)` itself REJECTS -- the Rust command refused before
     a turn ever started (no brain chosen, the endpoint could not be reached
     at dispatch, folder untrusted, etc). Handled entirely in the click
     handler's own `catch` block (see `send()` in ui/index.html, right above
     `go.addEventListener('click', send)`).
  2. A turn STARTS (`invoke('send')` resolves) and fails DURING the run --
     the model process exits non-zero, or emits to stderr. Handled by the
     `claude:stderr` / `claude:done` listeners and `addFailure()`.

Both are exercised here against a STUB carrying two configured, connected
providers (so a silent switch has somewhere to silently switch TO), and both
assert the same three things: the active provider is untouched afterward,
no second `send` was dispatched automatically, and the person was left a
real error with something to click.

A STATIC CHECK RIDES ALONG TOO (see `static_no_failover_code()`), because a
missing code path proves more than a passing behavioral test can: the
behavioral half can only prove THIS build didn't switch providers for THESE
two failure shapes, not that no such path exists anywhere in the file for a
shape nobody thought to simulate. Grepping for the mechanism itself (a call
to `select_provider` or a second `send` from inside a failure handler) is
what closes that gap.

WHO MAY RUN IT: anybody, locally. Contacts nothing outside this machine.
"""
import base64
import http.server
import json
import pathlib
import re
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


# Two connected providers, deliberately -- a silent switch needs somewhere to
# switch TO, and a STUB with only one provider could not tell the difference
# between "never switches" and "had nothing else to switch to".
STUB = r"""
window.__STATE__ = { ready:true, problem:null, path:'/usr/bin/claude',
  version:'2.1.250', detail:null, logged_in:true };
window.__PROV__ = { providers: [
  { id:'claude', kind:'claude', name:'Claude', base_url:'', model:'',
    builtin:true, connected:true, disconnected:false, checked_at:'',
    last_error:'', has_secret:false, caveat:'', migration_note:'' },
  { id:'backup-cloud', kind:'openai-compatible', name:'Backup Cloud',
    base_url:'https://api.example.com/v1', model:'gpt-x', builtin:false,
    connected:true, disconnected:false, checked_at:'', last_error:'',
    has_secret:true, caveat:'', migration_note:'' },
], active: 'claude' };
window.__SEND_CALLS__ = [];
window.__SEND_MODE__ = 'ok'; // 'ok' | 'reject'
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
  if (cmd === 'stop') return null;
  if (cmd === 'new_conversation') return null;
  if (cmd === 'send') {
    window.__SEND_CALLS__.push({ args, at: Date.now() });
    if (window.__SEND_MODE__ === 'reject') {
      throw 'Backup Cloud refused that — the key may be wrong, expired, or out of credit.';
    }
    return null;
  }
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


def static_no_failover_code():
    """The mechanism check, alongside the behavioral one -- see module doc.
    Greps the shipped file for the shape a silent failover would actually
    take: a `send`/`select_provider` invocation from inside the failure
    handlers themselves, rather than from a person clicking something."""
    text = (UI / "index.html").read_text()

    def block(start_marker, end_marker=None, span=1200):
        i = text.find(start_marker)
        if i < 0:
            return None
        return text[i:i + span]

    stderr_block = block("listen('claude:stderr'")
    done_block = block("listen('claude:done'")
    addfailure_block = block("function addFailure(text) {")

    ok = True
    for name, b in [("claude:stderr listener", stderr_block),
                     ("claude:done listener", done_block),
                     ("addFailure()", addfailure_block)]:
        if b is None:
            check(f"static: found {name}", False, "block not found at all")
            ok = False
            continue
        bad = re.search(r"invoke\(\s*['\"](send|select_provider)['\"]", b)
        check(f"static: {name} contains no auto-{{send,select_provider}} call",
              bad is None, bad.group(0) if bad else "")
        ok = ok and bad is None
    return ok


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

        print("== static: the failure handlers contain no auto-switch mechanism ==")
        static_no_failover_code()

        print("== 1. invoke('send') rejects at dispatch (backup provider unreachable) ==")
        cdp.js("provActive = 'backup-cloud'; window.__SEND_MODE__ = 'reject'; "
               "cwd.value = '/home/you/Documents/NameOS'; "
               "document.getElementById('prompt').value = 'hello'; true")
        cdp.js("send(); true")
        time.sleep(0.3)
        check("exactly one send() dispatch was made — no automatic retry on a "
              "different provider",
              cdp.js("window.__SEND_CALLS__.length") == 1,
              cdp.js("window.__SEND_CALLS__.length"))
        check("active provider is untouched after the rejection",
              cdp.js("provActive === 'backup-cloud'"))
        check("running was cleared, not left spinning",
              cdp.js("running === false"))
        check("a plain error line reached the feed",
              cdp.js("feed.querySelector('.turn.err') !== null"))
        check("the error names the provider that actually refused, not a "
              "generic failure",
              "Backup Cloud" in (cdp.js("feed.querySelector('.turn.err')?.textContent || ''") or ""))
        shoot(cdp, "provfail-01-dispatch-reject.png")

        print("== 2. a turn starts, then fails mid-run (claude:stderr + claude:done) ==")
        # ACTIVE PROVIDER IS THE NON-BUILTIN ONE ON PURPOSE. signInHint()'s
        # own kind==='claude' branch deliberately has NO action button (its
        # fix is "open a terminal", which this app cannot do for you) --
        # only the general "any other configured provider" branch offers
        # one (openBrainSheet). Using 'claude' here would be testing the
        # wrong branch and reporting an app fault that is actually a test
        # premise error; 'backup-cloud' is the shape most users' failures
        # actually take (an API-key provider gone bad).
        cdp.js("window.__SEND_MODE__ = 'ok'; window.__SEND_CALLS__ = []; "
               "provActive = 'backup-cloud'; document.getElementById('prompt').value = 'hello again'; true")
        cdp.js("send(); true")
        time.sleep(0.2)
        check("the turn actually started this time",
              cdp.js("window.__SEND_CALLS__.length") == 1)
        cdp.js("window.__LISTENERS__['claude:stderr'][0]({ payload: { text: "
               "'401 unauthorized: invalid api key' } }); true")
        cdp.js("window.__LISTENERS__['claude:done'][0]({ payload: { code: 1, session_id: null } }); true")
        time.sleep(0.2)
        check("still exactly one send() dispatch — the mid-run failure did not "
              "trigger a second, silent attempt on another provider",
              cdp.js("window.__SEND_CALLS__.length") == 1,
              cdp.js("window.__SEND_CALLS__.length"))
        check("active provider is untouched after the mid-run failure",
              cdp.js("provActive === 'backup-cloud'"))
        check("the person was left something to click, not just red text",
              cdp.js("feed.querySelector('.errAction') !== null"))
        action_text = cdp.js("feed.querySelector('.errAction')?.textContent || ''")
        check("the action opens the brain/connection settings (Check the "
              "connection / sign in), not a silent auto-fix",
              bool(action_text), repr(action_text))
        check("running was cleared on the failing done event",
              cdp.js("running === false"))
        shoot(cdp, "provfail-02-midrun-failure.png")

        print("== 3. that action button genuinely opens settings, doesn't just sit there ==")
        cdp.js("feed.querySelector('.errAction').click(); true")
        time.sleep(0.2)
        check("clicking it opened the brain sheet",
              cdp.js("!document.getElementById('brainSheet').hidden"))
        shoot(cdp, "provfail-03-action-opens-settings.png")

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
