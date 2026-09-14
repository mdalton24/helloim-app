#!/usr/bin/env python3
"""One-shot render harness for the UX review of ui/index.html. Serial, single
browser instance, closed at the end. Modelled on tour-check.py's CDP class."""
import base64, http.server, json, socket, socketserver, subprocess, sys
import threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UI = HERE / "ui"
SHOTS = HERE / "shots" / "wren-review"
VIEWPORT = (1280, 800)


def free_port():
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
        self.port, self.ws, self.n = port, None, 0

    def connect(self):
        import websocket
        for _ in range(80):
            try:
                tabs = json.load(urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json"))
                page = next(t for t in tabs if t["type"] == "page")
                self.ws = websocket.create_connection(
                    page["webSocketDebuggerUrl"], timeout=30)
                return
            except Exception:
                time.sleep(0.25)
        raise SystemExit("could not attach to Chromium over CDP")

    def send(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr,
                      returnByValue=True, awaitPromise=True)
        if r.get("exceptionDetails"):
            raise RuntimeError(f"JS threw: {r['exceptionDetails']}")
        return r["result"].get("value")


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    port, dport = free_port(), free_port()
    serve(port)

    proc = subprocess.Popen(
        ["/snap/bin/chromium", "--headless=new", f"--remote-debugging-port={dport}",
         f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}", "--hide-scrollbars",
         "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*",
         "--user-data-dir=/home/mdalton/.cache/nameos-wren-review",
         "--enable-unsafe-swiftshader",
         f"http://127.0.0.1:{port}/index.html"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        cdp = CDP(dport)
        cdp.connect()
        cdp.send("Runtime.enable")
        cdp.send("Page.enable")
        cdp.send("Page.addScriptToEvaluateOnNewDocument", source=r"""
          window.__TAURI__ = { core: { invoke: async (cmd) => {
            if (cmd === 'default_workdir') return '/home/mdalton/Documents/NameOS';
            if (cmd === 'is_folder') return true;
            if (cmd === 'preflight') return { ready: true, version: 'stub' };
            if (cmd === 'scan_notes') return { nodes: [], edges: [], truncated: false };
            if (cmd === 'load_profile') return { about:'', goal:'', memory:'',
              assistantName:'Sammy', personality:'', wakeWord:'' };
            if (cmd === 'list_connectors') return [];
            if (cmd === 'list_skills') return [];
            return null;
          } },
          event: { listen: () => {} },
          window: { getCurrentWindow: () => ({
            minimize(){}, toggleMaximize(){}, close(){}
          }) } };
          try { localStorage.setItem('nameos_tour_v1', '1'); } catch (e) {}
        """)
        cdp.send("Page.reload")
        time.sleep(2.0)

        def shot(name):
            png = cdp.send("Page.captureScreenshot", format="png")["data"]
            p = SHOTS / name
            p.write_bytes(base64.b64decode(png))
            print("wrote", p)
            return p

        cdp.js("""(() => {
          document.getElementById('authGate').hidden = true;
          document.getElementById('app').hidden = false;
          document.dispatchEvent(new CustomEvent('nameos:app-revealed'));
          return true;
        })()""")
        time.sleep(1.0)

        # 1. Main view: rail, top bar, chat panel empty state, brain backdrop.
        shot("01-main.png")

        # 2. Connections sheet.
        cdp.js("document.getElementById('connBtn').click()")
        time.sleep(0.5)
        shot("02-connections.png")
        cdp.js("document.getElementById('connSheetClose').click()")
        time.sleep(0.3)

        # 3. Skills sheet.
        cdp.js("document.getElementById('skillBtn').click()")
        time.sleep(0.5)
        shot("03-skills.png")
        cdp.js("document.getElementById('skillSheetClose').click()")
        time.sleep(0.3)

        # 4. About you sheet, "About you" tab (default).
        cdp.js("document.getElementById('aboutBtn').click()")
        time.sleep(0.5)
        shot("04-about-you.png")

        # 5. "About me" tab of the same sheet.
        cdp.js("document.getElementById('tabMe').click()")
        time.sleep(0.4)
        shot("05-about-me.png")
        cdp.js("document.getElementById('aboutCancel').click()")
        time.sleep(0.3)

        # 6. Permission menu open (rail dropdown).
        cdp.js("document.getElementById('modeToggle').click()")
        time.sleep(0.4)
        shot("06-permission-menu.png")
        cdp.js("document.getElementById('modeToggle').click()")
        time.sleep(0.2)

        # 7. Narrow window: does the rail / chat panel survive a small size.
        cdp.send("Emulation.setDeviceMetricsOverride", width=1000, height=700,
                 deviceScaleFactor=1, mobile=False)
        time.sleep(0.4)
        shot("07-narrow-1000.png")

    finally:
        proc.terminate()

    print("done")


if __name__ == "__main__":
    main()
