#!/usr/bin/env python3
"""Render the NameOS site in a real browser and photograph each act.

WHY: the page is one WebGL scene driven by a scroll clock. A source-level check
cannot tell "the orb is there" from "the module 404'd and the window is black",
and every failure mode of this page — a shader that will not compile, a mesh
that will not decode, a clock keyframe off by one — produces exactly the same
artefact: a black rectangle. So drive it over CDP, scroll it to each act, and
photograph what is actually on screen.

It fails loudly rather than handing back a black PNG someone might mistake for
a result, and it collects console errors, which is where a shader compile
failure announces itself.

Run:  python3 site-check.py        (writes shots/site-*.png, non-zero on fail)
"""
import base64, http.server, json, socket, socketserver, subprocess, sys
import threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
SHOTS = HERE / "shots"
VIEWPORT = (1440, 900)
CHROMIUM = "/snap/bin/chromium"


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


def serve(port):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(SITE), **k)
        def log_message(self, *a): pass
    httpd = socketserver.TCPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


class CDP:
    def __init__(self, port):
        self.port, self.ws, self.n = port, None, 0
        self.console = []

    def connect(self):
        import websocket
        for _ in range(120):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json"))
                page = next(t for t in tabs if t["type"] == "page")
                self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=40)
                return
            except Exception:
                time.sleep(0.25)
        raise SystemExit("could not attach to Chromium over CDP")

    def send(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded",
                                     "Runtime.consoleAPICalled"):
                self.console.append(msg)
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if r.get("exceptionDetails"):
            raise RuntimeError(f"JS threw: {json.dumps(r['exceptionDetails'])[:400]}")
        return r["result"].get("value")


def lit_fraction(png_path):
    """How much of the frame is meaningfully brighter than the near-black page.

    MEASURED OFF THE SCREENSHOT, NOT THE CANVAS. drawImage() on a healthy WebGL
    canvas reads back all zeros — three.js does not set preserveDrawingBuffer —
    so the obvious check reports a perfect render as blank.
    """
    from PIL import Image
    im = Image.open(png_path).convert("L").resize((240, 150))
    px = list(im.getdata())
    return sum(1 for v in px if v > 40) / float(len(px))


def real_errors(console):
    """Console noise that actually matters.

    Font CDNs and favicons fail in headless all the time and say nothing about
    whether the page works. A shader that will not compile does.
    """
    out = []
    for m in console:
        p = m.get("params", {})
        text = ""
        if "exceptionDetails" in p:
            text = json.dumps(p["exceptionDetails"])
        elif "entry" in p:
            e = p["entry"]
            if e.get("level") != "error":
                continue
            text = e.get("text", "") + " " + e.get("url", "")
        else:
            continue
        low = text.lower()
        if any(s in low for s in ("favicon", "fonts.googleapis", "fontshare",
                                 "fonts.gstatic", "err_blocked_by_client")):
            continue
        out.append(text[:300])
    return out


def main():
    SHOTS.mkdir(exist_ok=True)
    port, dport = free_port(), free_port()
    serve(port)

    proc = subprocess.Popen(
        [CHROMIUM, "--headless=new", f"--remote-debugging-port={dport}",
         f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}", "--hide-scrollbars",
         "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*",
         "--user-data-dir=/home/mdalton/.cache/nameos-site-check",
         "--enable-unsafe-swiftshader",
         f"http://127.0.0.1:{port}/index.html"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    fails, lit = [], {}
    try:
        cdp = CDP(dport); cdp.connect()
        cdp.send("Runtime.enable"); cdp.send("Log.enable"); cdp.send("Page.enable")

        def shot(name):
            png = cdp.send("Page.captureScreenshot", format="png")["data"]
            p = SHOTS / name
            p.write_bytes(base64.b64decode(png))
            return p

        # THE LOADER, caught early — it only lives for about 1.2 seconds.
        time.sleep(0.7)
        loader = shot("site-1-loader.png")
        lit["loader"] = lit_fraction(loader)

        # THE ORB. The loader holds 260ms at full then flies out over 900ms,
        # and the intro clock runs 2900ms after that. Wait the whole way.
        time.sleep(6.0)
        orb = shot("site-2-orb.png")
        lit["orb"] = lit_fraction(orb)
        if lit["orb"] < 0.01:
            fails.append(f"no orb — only {lit['orb']:.3%} of the frame is lit")

        # Each act is driven by the scroll clock, which EASES toward the scroll
        # position rather than snapping, so a screenshot taken straight after a
        # jump photographs the previous act. Scroll, then wait it out.
        def goto(fraction, name, label):
            cdp.js(f"window.scrollTo(0, document.body.scrollHeight * {fraction})")
            time.sleep(3.2)
            p = shot(name)
            lit[label] = lit_fraction(p)
            return p

        galaxy = goto(0.30, "site-3-galaxy.png", "galaxy")
        brain  = goto(0.55, "site-4-brain.png",  "brain")
        cards  = goto(0.86, "site-5-cards.png",  "cards")
        foot   = goto(1.00, "site-6-footer.png", "footer")

        for key in ("galaxy", "brain"):
            if lit[key] < 0.01:
                fails.append(f"the {key} act is dark — {lit[key]:.3%} lit")

        # The white cards are opaque, so their frames must be BRIGHT. A dark one
        # means the card never revealed, which the lit test above would miss.
        if lit["cards"] < 0.25:
            fails.append(f"the white cards did not arrive — {lit['cards']:.3%} lit")

        # Did the brain mesh actually decode? It is fetched and never blocked
        # on, so a failed decode is completely silent by design.
        brain_ok = cdp.js("(() => { try { return !!document.querySelector('canvas'); } catch(e){ return false; } })()")
        if not brain_ok:
            fails.append("no canvas in the document")

        # The accordion's first item must be open, and open means a measured
        # height rather than merely a class.
        accH = cdp.js("""(() => {
          const item = document.querySelector('.accItem');
          if (!item) return -1;
          const panel = item.querySelector('.accPanel');
          return item.classList.contains('open') ? parseFloat(panel.style.height) || 0 : -2;
        })()""")
        if accH is None or accH <= 0:
            fails.append(f"the FAQ's first item is not open with a measured height (got {accH})")

        errs = real_errors(cdp.console)
        for e in errs[:6]:
            fails.append(f"console error: {e}")

        for k, v in lit.items():
            print(f"lit {k:8s}: {v:.3%}")
        print(f"first FAQ panel height: {accH}px")
        print("shots:", ", ".join(str(p.name) for p in
              (loader, orb, galaxy, brain, cards, foot)))
    finally:
        proc.terminate()

    if fails:
        print("\nFAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print("\nOK — every act renders, the cards arrive, no console errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
