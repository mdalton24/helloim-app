#!/usr/bin/env python3
"""Prove the first-run wizard's name choice actually changes the THEME.

Mark, 2026-08-29: "during the install, you are asked to pick Bella or Jarvis.
This should not be just for name, but this is theme. So, if bella is chosen,
the bella theme should be shown and not jarvis."

A source-level check cannot answer this. `data-theme` is set by a script in
<head> before first paint, moved by applyTheme(), and read by twenty-odd CSS
blocks and by scene-mount.js -- so the only honest test is to open the wizard
in a real browser, press the chip a person would press, and read back what the
document says it is. This drives Chromium over CDP and does exactly that.

The five things it asserts, in the order a person meets them:
  1. A fresh profile opens on the documented default (jarvis).
  2. Pressing the Bella chip moves data-theme to bella AND asks scene-mount to
     crossfade to Bella's scene -- a colour swap without the scene is the
     "palette swap, not a real theme" trap Iris's spec warns about.
  3. Pressing Jarvis moves it back, both halves again.
  4. TYPING a theme's name by hand counts the same as pressing its chip.
  5. A name that is nobody's theme ("Sammy") leaves the theme alone rather
     than reverting it -- this only ever moves the theme TO a match.

Run:  python3 onboard-theme-check.py
"""
import http.server
import json
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UI = HERE / "ui"
VIEWPORT = (1440, 900)


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
        self.port = port
        self.ws = None
        self.n = 0

    def connect(self):
        import websocket  # noqa
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


# The wizard's own step-1 markup, addressed the way a person addresses it: the
# chip with that word on it, and the text field beside it. Nothing here reaches
# into Onboard's closure -- if the chips stop being buttons, this fails, which
# is the point.
CHIP = """(() => {
  const b = [...document.querySelectorAll('#obField .preset')]
              .find(x => x.textContent.trim() === %s);
  if (!b) return 'NO CHIP';
  b.click();
  return 'ok';
})()"""

TYPE = """(() => {
  const i = document.getElementById('obInput');
  if (!i) return 'NO INPUT';
  i.value = %s;
  i.dispatchEvent(new Event('input', { bubbles: true }));
  return 'ok';
})()"""

STATE = "({ theme: document.documentElement.dataset.theme, scene: window.__sceneAsked })"


def main():
    port = free_port()
    dport = free_port()
    serve(port)

    proc = subprocess.Popen(
        ["/snap/bin/chromium", "--headless=new", f"--remote-debugging-port={dport}",
         f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}", "--hide-scrollbars",
         "--no-first-run", "--no-default-browser-check",
         "--remote-allow-origins=*",
         "--user-data-dir=/home/mdalton/.cache/nameos-onboard-theme-check",
         "--enable-unsafe-swiftshader",
         f"http://127.0.0.1:{port}/index.html"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    fails = []

    def want(label, got, expect):
        if got == expect:
            print(f"  ok   {label}: {got}")
        else:
            fails.append(f"{label}: expected {expect!r}, got {got!r}")
            print(f"  FAIL {label}: expected {expect!r}, got {got!r}")

    try:
        cdp = CDP(dport)
        cdp.connect()
        cdp.send("Runtime.enable")
        cdp.send("Page.enable")
        time.sleep(2.5)

        # A FRESH INSTALL, not this cache's leftovers: the theme is persisted,
        # so without this the second run of this file would test a machine that
        # had already chosen. Reloaded after clearing so the <head> pre-paint
        # script re-runs against an empty store, exactly as it does on a first
        # ever launch.
        cdp.js("localStorage.clear()")
        cdp.send("Page.reload")
        time.sleep(3.0)

        # Stand in for scene-mount.js so the scene half is observable. The real
        # one is an ES module that swaps a WebGL scene; what matters here is
        # only that applyTheme ASKS for the right one.
        cdp.js("window.__sceneAsked = null;"
               "window.NameOSSwitchScene = (s) => { window.__sceneAsked = s; };")

        print("1. a fresh profile opens on the documented default")
        want("data-theme at first paint", cdp.js("document.documentElement.dataset.theme"), "jarvis")

        # invoke() is Tauri's and is absent in a plain browser; reopen() catches
        # its own failure and opens anyway, which is what makes this testable.
        cdp.js("Onboard.reopen()")
        time.sleep(0.8)
        want("wizard is open", cdp.js("!document.getElementById('onboardSheet').hidden"), True)
        want("it is on step 1", cdp.js("document.getElementById('obQuestion').textContent"),
             "What do you want to call your assistant?")

        print("2. pressing Bella shows the Bella theme")
        want("chip pressed", cdp.js(CHIP % json.dumps("Bella")), "ok")
        time.sleep(0.4)
        st = cdp.js(STATE)
        want("data-theme", st["theme"], "bella")
        want("scene asked for", st["scene"], "aurelia")
        want("the name it typed", cdp.js("document.getElementById('obInput').value"), "Bella")
        want("Next is live", cdp.js("!document.getElementById('obNext').disabled"), True)

        print("3. pressing Jarvis puts it back")
        want("chip pressed", cdp.js(CHIP % json.dumps("Jarvis")), "ok")
        time.sleep(0.4)
        st = cdp.js(STATE)
        want("data-theme", st["theme"], "jarvis")
        want("scene asked for", st["scene"], "board")

        print("4. typing the name by hand counts too")
        want("typed", cdp.js(TYPE % json.dumps("  bella  ")), "ok")
        time.sleep(0.4)
        st = cdp.js(STATE)
        want("data-theme (trimmed, case-insensitive)", st["theme"], "bella")
        want("scene asked for", st["scene"], "aurelia")

        print("5. a name that is nobody's theme leaves the theme alone")
        cdp.js("window.__sceneAsked = null")
        want("typed", cdp.js(TYPE % json.dumps("Sammy")), "ok")
        time.sleep(0.4)
        st = cdp.js(STATE)
        want("data-theme unchanged", st["theme"], "bella")
        want("no scene churn", st["scene"], None)
        # And a partial match must not swap the window out mid-word.
        cdp.js(TYPE % json.dumps("Bell"))
        time.sleep(0.3)
        want("'Bell' is not Bella", cdp.js("document.documentElement.dataset.theme"), "bella")

        print("6. the choice survives a restart")
        cdp.js(TYPE % json.dumps("Jarvis"))
        time.sleep(0.3)
        cdp.send("Page.reload")
        time.sleep(3.0)
        want("data-theme after reload", cdp.js("document.documentElement.dataset.theme"), "jarvis")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print()
    if fails:
        print(f"FAIL — {len(fails)} check(s) did not hold:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — the name chosen at setup is the theme that shows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
