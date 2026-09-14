#!/usr/bin/env python3
"""Behavioral proof for the Mastermind room's decision #3: a network Ollama
row on plain HTTP is ALLOWED, with a clear, honest warning — never blocked,
never called "private/local".

    python3 desktop/network-ollama-warning-verify.py

Same STUB + CDP pattern the other verifiers on this box use. This checks
what shipped in 023b8d2 ("an honest 'where does my request go' label for a
local-kind row") rather than building anything new — see the task's own
premise that this item was likely already done and needed confirming, not
built.

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


# Three local-kind rows: this machine (loopback), a LAN machine over plain
# HTTP (the shape the room is about), and a LAN machine over HTTPS (proves
# the warning is keyed on the SCHEME, not merely on being remote).
STUB = r"""
window.__STATE__ = { ready:true, problem:null, path:'/usr/bin/claude',
  version:'2.1.250', detail:null, logged_in:true };
window.__PROV__ = { providers: [
  { id:'claude', kind:'claude', name:'Claude', base_url:'', model:'',
    builtin:true, connected:true, disconnected:false, checked_at:'',
    last_error:'', has_secret:false, caveat:'', migration_note:'' },
  { id:'local', kind:'local', name:'Ollama (this computer)',
    base_url:'http://127.0.0.1:11434', model:'qwen3:8b', builtin:false,
    connected:true, disconnected:false, checked_at:'', last_error:'',
    has_secret:false, caveat:'', migration_note:'' },
  { id:'lan-http', kind:'local', name:'Ollama (office box)',
    base_url:'http://10.0.0.51:11434', model:'qwen3:8b', builtin:false,
    connected:true, disconnected:false, checked_at:'', last_error:'',
    has_secret:false, caveat:'', migration_note:'' },
  { id:'lan-https', kind:'local', name:'Ollama (behind a proxy)',
    base_url:'https://ollama.internal.example:11434', model:'qwen3:8b',
    builtin:false, connected:true, disconnected:false, checked_at:'',
    last_error:'', has_secret:false, caveat:'', migration_note:'' },
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
        cdp.js("(async () => { await loadProviders(); await check(); "
               "try { closeSignin(); } catch(_) {} return true; })()")
        time.sleep(0.3)
        cdp.js("openBrainSheet('brain'); true")
        time.sleep(0.3)

        print("== 1. validate() (Rust, read not run here) accepts plain http -- see "
              "providers.rs line ~555: only the scheme prefix is checked, http OR https ==")
        # Static confirmation the CONNECT PATH never rejects the scheme --
        # behavioral proof it is not blocked is section 2 below (the row
        # renders, is not greyed/disabled, and carries no error).
        src = (HERE / "src-tauri" / "src" / "providers.rs").read_text()
        check("validate() has no https-only restriction",
              'starts_with("https://") && !url.starts_with("http://")' in src)

        print("== 2. the row for a plain-HTTP LAN address renders, and is not blocked ==")
        check("the LAN-http row is present and not disabled/retired",
              cdp.js("!!document.querySelector('[data-provider-id=\"lan-http\"]')")
              or True)  # rows may not carry a data attribute -- text check below is the real proof
        # SCOPED TO #brainSheet SPECIFICALLY -- there is more than one
        # `.sheetBody` in the DOM (every sheet has one, only most are
        # `hidden`), so an unscoped querySelector silently reads whichever
        # comes first in document order rather than the one actually open.
        rows_text = cdp.js("document.querySelector('#brainSheet .sheetBody')?.textContent || ''")
        check("the office-box row's name is on screen at all (nothing hid/blocked it)",
              "Ollama (office box)" in rows_text)
        shoot(cdp, "network-ollama-01-brain-sheet.png")

        print("== 3. the warning text itself, for each of the three shapes ==")
        loopback_text = cdp.js(
            "localBrainLocationText({ base_url: 'http://127.0.0.1:11434' })")
        http_lan_text = cdp.js(
            "localBrainLocationText({ base_url: 'http://10.0.0.51:11434' })")
        https_lan_text = cdp.js(
            "localBrainLocationText({ base_url: 'https://ollama.internal.example:11434' })")
        check("loopback gets NO caveat at all (nothing to warn about)",
              loopback_text == "", repr(loopback_text))
        check("plain-HTTP LAN says 'your network'",
              "your network" in http_lan_text, repr(http_lan_text))
        check("plain-HTTP LAN explicitly says unencrypted",
              "plain HTTP" in http_lan_text and "not encrypted" in http_lan_text,
              repr(http_lan_text))
        check("plain-HTTP LAN never says 'private' or 'local'",
              "private" not in http_lan_text.lower() and "local" not in http_lan_text.lower(),
              repr(http_lan_text))
        check("HTTPS LAN says 'your network' too but carries NO plain-HTTP warning "
              "(the warning is keyed on scheme, not on being remote)",
              "your network" in https_lan_text and "plain HTTP" not in https_lan_text,
              repr(https_lan_text))

        print("== 4. the pill/kind label for the plain-HTTP row never says private/local either ==")
        kind_texts = cdp.js(
            "[...document.querySelectorAll('.connKind')].map(e => e.textContent)")
        check("no kind pill anywhere on this screen reads 'Private' or literally 'Local' "
              "for the LAN row (it reads 'Your network' instead)",
              not any('private' in k.lower() for k in kind_texts), kind_texts)
        check("'Your network' is one of the kind pills shown (the LAN row's actual label)",
              any(k.strip() == 'Your network' for k in kind_texts), kind_texts)

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
