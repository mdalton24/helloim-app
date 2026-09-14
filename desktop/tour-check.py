#!/usr/bin/env python3
"""Walk the first-run tour in a real browser and prove the ring lands on the control.

WHY THIS EXISTS, AND WHY IT IS NOT A grep. A spotlight tour has exactly one
interesting failure and source cannot see it: the ring lands somewhere the
control is not. Every id can be correct, every string can be present, the
positioning maths can be off by one branch, and what the person gets is a
glowing rectangle over empty space next to the button it is describing. So this
drives the real page, walks all five stops, and for each one MEASURES the
spotlight against the control's own bounding box.

It also checks the two things a card gets wrong: falling off the window, and
sitting on top of the very control it is pointing at.

Run:  python3 tour-check.py       (writes shots/tour-*.png, non-zero on failure)
"""
import base64, http.server, json, socket, socketserver, subprocess, sys
import threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UI = HERE / "ui"
SHOTS = HERE / "shots"
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
        self.port, self.ws, self.n = port, None, 0

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


# The stops, in the order the tour walks them. Duplicated from index.html on
# purpose: a test that imports the thing it is testing agrees with it by
# construction, including when both are wrong.
EXPECTED = [
    ("prompt", "Everything starts here"),
    ("mic", "Or just say it"),
    ("folderBar", "This is what it can see"),
    ("modeToggle", "How much rope it gets"),
    ("aboutBtn", "Make it yours"),
    ("connBtn", "Where you plug things in"),
    ("skillBtn", "Teach it something"),
]

MEASURE = """(() => {
  const box = (n) => { const r = n.getBoundingClientRect();
    return { t: r.top, l: r.left, w: r.width, h: r.height, b: r.bottom, r: r.right }; };
  const spot = document.getElementById('tourSpot');
  const card = document.getElementById('tourCard');
  const target = document.getElementById('%s');
  if (!target) return null;
  return {
    hidden: document.getElementById('tour').hidden,
    spot: box(spot), card: box(card), target: box(target),
    title: document.getElementById('tourTitle').textContent,
    body: document.getElementById('tourBody').textContent,
    dots: document.querySelectorAll('.tourDot').length,
    lit: document.querySelectorAll('.tourDot.on').length,
    // WHICH dot is lit, not how many. The dots are a position indicator, so
    // exactly one is on and the interesting question is whether it is the
    // right one — an off-by-one here would show someone the wrong place in
    // the tour while the card said something else.
    litAt: [...document.querySelectorAll('.tourDot')].findIndex(d => d.classList.contains('on')),
    vw: innerWidth, vh: innerHeight,
  };
})()"""


def main():
    SHOTS.mkdir(exist_ok=True)
    port, dport = free_port(), free_port()
    serve(port)

    proc = subprocess.Popen(
        ["/snap/bin/chromium", "--headless=new", f"--remote-debugging-port={dport}",
         f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}", "--hide-scrollbars",
         "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*",
         "--user-data-dir=/home/mdalton/.cache/nameos-tour-check",
         "--enable-unsafe-swiftshader",
         f"http://127.0.0.1:{port}/index.html"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    fails = []
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
            return null;
          } }, event: { listen: () => {} } };
          // A returning user has this set; the tour must be a first-run thing.
          try { localStorage.removeItem('nameos_tour_v1'); } catch (e) {}
        """)
        cdp.send("Page.reload")
        time.sleep(2.5)

        def shot(name):
            png = cdp.send("Page.captureScreenshot", format="png")["data"]
            p = SHOTS / name
            p.write_bytes(base64.b64decode(png))
            return p

        # Sign in the way revealApp() does, INCLUDING the event — that event is
        # the whole trigger, and a check that called Tour.start() by hand would
        # pass on a build where nothing ever starts the tour.
        cdp.js("""(() => {
          document.getElementById('authGate').hidden = true;
          document.getElementById('app').hidden = false;
          document.dispatchEvent(new CustomEvent('nameos:app-revealed'));
          return true;
        })()""")

        # The tour waits 650ms for the reveal to settle, on purpose.
        time.sleep(2.0)
        if cdp.js("document.getElementById('tour').hidden"):
            fails.append("the tour never started — #tour is still hidden two "
                         "seconds after the app was revealed")

        for i, (target_id, title) in enumerate(EXPECTED):
            m = cdp.js(MEASURE % target_id)
            if m is None:
                fails.append(f"step {i+1}: #{target_id} is not in the document")
                break
            shot(f"tour-{i+1}-{target_id}.png")

            if m["hidden"]:
                fails.append(f"step {i+1}: the tour is hidden but should be showing "
                             f"{target_id}")
                break
            if m["title"] != title:
                fails.append(f"step {i+1}: expected the card to read {title!r}, "
                             f"got {m['title']!r} — the order or the copy has moved")
            if m["dots"] != len(EXPECTED) or m["lit"] != 1 or m["litAt"] != i:
                fails.append(f"step {i+1}: the dots read {m['lit']} lit at index "
                             f"{m['litAt']} of {m['dots']}, expected exactly one "
                             f"lit at index {i} of {len(EXPECTED)}")

            # THE REAL CHECK. The ring is drawn 8px outside the control, so it
            # must contain it. A tolerance of 2px absorbs sub-pixel layout;
            # anything worse than that is the spotlight on the wrong thing.
            s, t = m["spot"], m["target"]
            tol = 2
            if not (s["t"] <= t["t"] + tol and s["l"] <= t["l"] + tol
                    and s["b"] >= t["b"] - tol and s["r"] >= t["r"] - tol):
                fails.append(
                    f"step {i+1}: the spotlight is not on #{target_id}. "
                    f"ring {s['l']:.0f},{s['t']:.0f} {s['w']:.0f}x{s['h']:.0f} vs "
                    f"control {t['l']:.0f},{t['t']:.0f} {t['w']:.0f}x{t['h']:.0f}")

            # The card has to be readable: fully on screen...
            c = m["card"]
            if c["t"] < 0 or c["l"] < 0 or c["b"] > m["vh"] or c["r"] > m["vw"]:
                fails.append(
                    f"step {i+1}: the card is off screen — "
                    f"{c['l']:.0f},{c['t']:.0f} to {c['r']:.0f},{c['b']:.0f} "
                    f"in a {m['vw']}x{m['vh']} window")
            # ...and not sitting on the control it is describing.
            if not (c["r"] < s["l"] or c["l"] > s["r"]
                    or c["b"] < s["t"] or c["t"] > s["b"]):
                fails.append(f"step {i+1}: the card overlaps the spotlight, so it "
                             f"covers the control it is pointing at")

            cdp.js("document.getElementById('tourNext').click()")
            time.sleep(0.55)   # the ring's travel is 320ms

        # After the last stop it should be gone, and stay gone next launch.
        if not cdp.js("document.getElementById('tour').hidden"):
            fails.append("the tour did not close after the final step")
        if cdp.js("localStorage.getItem('nameos_tour_v1')") != "1":
            fails.append("finishing the tour did not record that it was seen — "
                         "it would run again on every launch")

        # ...but it must still be askable-for. This is the one people lose.
        # The RAIL button, not the empty-feed link. The link is gone as soon as
        # anything lands in the feed — which in this run is a note about the
        # microphone, and in real use is the first answer.
        cdp.js("document.getElementById('tourHelp').click()")
        time.sleep(0.6)
        if cdp.js("document.getElementById('tour').hidden"):
            fails.append("the rail's 'Show me around' does not restart the "
                         "tour, so a dismissed tour is gone forever")
        else:
            shot("tour-replay.png")

        # Escape is the way out of anything modal, and someone will press it.
        cdp.send("Input.dispatchKeyEvent", type="keyDown", key="Escape",
                 code="Escape", windowsVirtualKeyCode=27, nativeVirtualKeyCode=27)
        cdp.send("Input.dispatchKeyEvent", type="keyUp", key="Escape",
                 code="Escape", windowsVirtualKeyCode=27, nativeVirtualKeyCode=27)
        time.sleep(0.4)
        if not cdp.js("document.getElementById('tour').hidden"):
            fails.append("Escape does not close the tour")
    finally:
        proc.terminate()

    if fails:
        print("TOUR CHECK FAILED")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print(f"tour check passed — {len(EXPECTED)} stops, shots in {SHOTS}")


if __name__ == "__main__":
    main()
