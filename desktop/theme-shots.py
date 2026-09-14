#!/usr/bin/env python3
"""Screenshot NameOS for the theme-system build (Wren, 2026-08-28).

ONE chromium at a time, serially -- the box went down on 2026-08-23 when
several ran at once (see CLAUDE.md). Modelled on design-shots.py's own CDP
harness, trimmed to what this specific build needs to prove:

  before   -- 01-main at 1180x800 and 720x520, current index.html, UNTOUCHED.
              The baseline Phase 1 has to reproduce exactly.
  after    -- same two shots, post Phase-1 tokenisation. Diffed against
              'before' with PIL -- 0 changed pixels is the proof, not a look.
  jarvis   -- the Jarvis theme at 1180x800, 720x520, 1600x1000 and the
              sub-900x620 case (860x600), plus the theme menu open in both
              themes and a console-error capture.

Run:  python3 theme-shots.py before
      python3 theme-shots.py after
      python3 theme-shots.py jarvis
"""
import base64, http.server, json, socketserver, subprocess, sys, threading, time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UI = HERE / "ui"
OUT = HERE / "shots" / "theme"
OUT.mkdir(parents=True, exist_ok=True)

TAURI_STUB = r"""
  window.__TAURI__ = { core: { invoke: async (cmd) => {
    if (cmd === 'default_workdir') return 'C:\\Users\\mdalt\\Documents\\NameOS';
    if (cmd === 'is_folder') return true;
    if (cmd === 'preflight') return { ready: true, version: '2.1.246' };
    if (cmd === 'scan_notes') return { nodes: [], edges: [], truncated: false };
    if (cmd === 'load_profile') return { about:'', goal:'', memory:'',
      assistantName:'Jarvis', personality:'', wakeWord:'' };
    if (cmd === 'check_update') return { available:false, currentVersion:'0.1.0' };
    if (cmd === 'is_running') return false;
    if (cmd === 'list_skills') return [];
    if (cmd === 'list_facts') return [];
    if (cmd === 'memory_stats') return { total:0, assistantCount:0, verifiedCount:0 };
    if (cmd === 'list_providers') return { active: 'p-local', providers: [] };
    if (cmd === 'detect_local_brain') return { running:false, apiOk:false, version:'', models:[], problem:null };
    if (cmd === 'list_plugins') return [];
    if (cmd === 'list_connectors') return [
      { id:'a', kind:'api', name:'Claude', provider:'anthropic', baseUrl:'', model:'',
        args:[], connected:true, checkedAt:String(Math.floor(Date.now()/1000)-60), lastError:'', hasSecret:true },
      { id:'b', kind:'api', name:'Gmail', provider:'google', baseUrl:'', model:'',
        args:[], connected:true, checkedAt:String(Math.floor(Date.now()/1000)-500), lastError:'', hasSecret:true },
      { id:'c', kind:'api', name:'Ollama', provider:'openai', baseUrl:'http://127.0.0.1:11434', model:'',
        args:[], connected:true, checkedAt:String(Math.floor(Date.now()/1000)-90), lastError:'', hasSecret:false },
      { id:'d', kind:'api', name:'OpenAI', provider:'openai', baseUrl:'https://api.openai.com/v1', model:'',
        args:[], connected:false, checkedAt:'', lastError:'', hasSecret:true },
      { id:'e', kind:'mcp', name:'Notion', provider:'', command:'npx', args:[],
        connected:false, checkedAt:'', lastError:'', hasSecret:false },
      { id:'f', kind:'api', name:'Workshop endpoint', provider:'openai',
        baseUrl:'https://example.invalid/v1', model:'', args:[], connected:false,
        checkedAt:String(Math.floor(Date.now()/1000)-300), lastError:'401 invalid api key', hasSecret:true },
    ];
    return null;
  } }, event: { listen: () => {} } };
  const QuietRecognition = function () {
    this.continuous=false; this.interimResults=false; this.lang='en-US';
    this.onresult=null; this.onerror=null; this.onend=null; this.onstart=null; this.onaudiostart=null;
    this.start=function(){}; this.stop=function(){}; this.abort=function(){};
    this.addEventListener=function(){}; this.removeEventListener=function(){};
  };
  window.SpeechRecognition = QuietRecognition;
  window.webkitSpeechRecognition = QuietRecognition;
"""

CLOSE_ALL = """(() => {
  for (const id of ['connSheetClose','aboutClose','updateClose','skillSheetClose']) {
    const b = document.getElementById(id);
    if (b && b.click) { try { b.click(); } catch (e) {} }
  }
  for (const s of document.querySelectorAll('.sheet')) s.hidden = true;
  return true;
})()"""


def free_port():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def serve(port):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k): super().__init__(*a, directory=str(UI), **k)
        def log_message(self, *a): pass
    httpd = socketserver.TCPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


class CDP:
    def __init__(self, port): self.port = port; self.n = 0; self.ws = None
    def connect(self):
        import websocket
        for _ in range(60):
            try:
                tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json").read())
                pages = [t for t in tabs if t["type"] == "page"]
                if pages:
                    self.ws = websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=40)
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
                if "error" in m: raise SystemExit(f"{method}: {m['error']}")
                return m.get("result", {})
    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")


def shot(cdp, w, h, name, pre_js=""):
    cdp.send("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=2, mobile=False)
    time.sleep(0.6)
    cdp.js(CLOSE_ALL)
    if pre_js:
        cdp.js(f"(() => {{ {pre_js}; return true; }})()")
    time.sleep(0.9)
    png = cdp.send("Page.captureScreenshot", format="png")["data"]
    p = OUT / f"{name}.png"
    p.write_bytes(base64.b64decode(png))
    print(f"  {p.name}")
    return p


def run(cases):
    port, dport = free_port(), free_port()
    httpd = serve(port)
    proc = subprocess.Popen(
        ["/snap/bin/chromium", "--headless=new", f"--remote-debugging-port={dport}",
         "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         "--remote-allow-origins=*", "--window-size=1180,800",
         f"http://127.0.0.1:{port}/index.html"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    errs = []
    try:
        cdp = CDP(dport); cdp.connect()
        cdp.send("Runtime.enable"); cdp.send("Page.enable")
        cdp.send("Page.addScriptToEvaluateOnNewDocument", source=TAURI_STUB)
        cdp.send("Page.reload")
        time.sleep(3.0)
        cdp.js("""(() => {
          const g = document.getElementById('authGate'); const a = document.getElementById('app');
          if (g) g.hidden = true; if (a) a.hidden = false; return true;
        })()""")
        time.sleep(1.2)
        for fn in cases:
            fn(cdp)
        # console errors, best-effort drain -- short timeout so this cannot hang
        cdp.ws.settimeout(0.4)
        try:
            while True:
                m = json.loads(cdp.ws.recv())
                if m.get("method") == "Runtime.exceptionThrown":
                    errs.append(m["params"]["exceptionDetails"].get("text", "?"))
        except Exception:
            pass
    finally:
        proc.terminate()
    if errs:
        print("CONSOLE ERRORS:")
        for e in errs: print(" ", e)
    return errs


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "before"

    if mode in ("before", "after"):
        run([lambda cdp: shot(cdp, 1180, 800, f"{mode}-bella-main--1180x800"),
             lambda cdp: shot(cdp, 720, 520, f"{mode}-bella-main--720x520")])

    elif mode == "diff":
        from PIL import Image, ImageChops
        for size in ("1180x800", "720x520"):
            a = Image.open(OUT / f"before-bella-main--{size}.png").convert("RGB")
            b = Image.open(OUT / f"after-bella-main--{size}.png").convert("RGB")
            if a.size != b.size:
                print(f"{size}: SIZE MISMATCH {a.size} vs {b.size}"); continue
            diff = ImageChops.difference(a, b)
            bbox = diff.getbbox()
            hist = diff.convert("L").histogram()
            nonzero = sum(hist[1:])
            total = a.size[0] * a.size[1]
            print(f"{size}: bbox={bbox} nonzero-pixels(any-channel-diff)={nonzero}/{total*3}")

    elif mode == "jarvis":
        run([
            lambda cdp: cdp.js("localStorage.setItem('nameos_theme','jarvis'); location.reload()"),
            lambda cdp: time.sleep(2.5),
            lambda cdp: cdp.js("""(() => {
              const g=document.getElementById('authGate'); const a=document.getElementById('app');
              if (g) g.hidden=true; if (a) a.hidden=false; return true; })()"""),
            lambda cdp: time.sleep(1.5),
            lambda cdp: shot(cdp, 1180, 800, "jarvis-main--1180x800"),
            lambda cdp: shot(cdp, 720, 520, "jarvis-main--720x520"),
            lambda cdp: shot(cdp, 1600, 1000, "jarvis-main--1600x1000"),
            lambda cdp: shot(cdp, 860, 600, "jarvis-main--860x600-subchip"),
            lambda cdp: shot(cdp, 1180, 800, "jarvis-menu--1180x800",
                              "document.getElementById('themeBtn').click()"),
            lambda cdp: shot(cdp, 720, 520, "jarvis-menu--720x520",
                              "document.getElementById('themeBtn').click()"),
            lambda cdp: shot(cdp, 1180, 800, "bella-menu-from-jarvis--1180x800",
                              "document.getElementById('themeBtn').click();"
                              "setTimeout(()=>{document.querySelector('[data-theme-id=\"bella\"]')?.click();},300)"),
        ])

    else:
        print(f"unknown mode {mode!r}"); sys.exit(1)


if __name__ == "__main__":
    main()
