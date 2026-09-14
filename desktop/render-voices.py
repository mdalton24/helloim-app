#!/usr/bin/env python3
"""Photograph the natural-voice menu, because building it is not seeing it.

The Rust side is proven separately by `tts_probe` — it makes real audio and
whisper reads it back. This proves the OTHER half: that the menu Mark asked for
actually draws, groups, and puts a play button on every row.

IT STUBS THE TAURI BRIDGE, and that limit is stated rather than hidden. In a
browser there is no `window.__TAURI__`, so the panel would draw empty and the
screenshot would look like a bug. The stub answers `tts_status` and `tts_voices`
with the REAL voice ids read out of the installed pack — so the list, the
grouping and the labels are the true ones; only the transport is fake.

Run:  python3 render-voices.py      (writes shots/voices-*.png, non-zero on fail)
"""
import base64, http.server, json, os, socket, socketserver, subprocess, sys
import threading, time, urllib.request, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
UI = HERE / "ui"
SHOTS = HERE / "shots"
PACK = Path.home() / ".local/share/ai.nameos.desktop/tts/voices.bin"
VIEWPORT = (1440, 980)


def voice_ids():
    if not PACK.is_file():
        sys.exit(f"no voice pack at {PACK} — install it first")
    with zipfile.ZipFile(PACK) as z:
        return sorted(n[:-4] if n.endswith(".npy") else n for n in z.namelist())


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


def cdp(dport):
    for _ in range(100):
        try:
            tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{dport}/json"))
            # THE TYPE CHECK IS NOT TIDINESS. Without it this grabbed whatever
            # target answered last — often not the page — so Page.enable and the
            # injected bridge went somewhere harmless and this script reported an
            # empty menu for a menu that was drawing all 54 rows correctly.
            # A checker that fails for its own reasons is worse than no checker.
            for t in tabs:
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    return t["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.1)
    sys.exit("chromium never opened a debugging port")


def main():
    import websocket  # noqa

    ids = voice_ids()
    port, dport = free_port(), free_port()
    serve(port)

    # Injected before any page script runs, so the app finds a bridge already
    # there rather than deciding there isn't one.
    stub = """
    (() => {
      const VOICES = %s;
      const ACCENT = {a:'American',b:'British',e:'Spanish',f:'French',h:'Hindi',
                      i:'Italian',j:'Japanese',p:'Portuguese',z:'Chinese'};
      const list = VOICES.map(id => {
        const [pre, given] = id.includes('_') ? id.split('_') : ['', id];
        const label = given.charAt(0).toUpperCase() + given.slice(1);
        return { id, label, accent: ACCENT[pre[0]] || '',
                 gender: pre[1] === 'f' ? 'f' : pre[1] === 'm' ? 'm' : '' };
      }).sort((x, y) => (x.accent + x.label).localeCompare(y.accent + y.label));
      window.__TAURI__ = {
        core: { invoke: (cmd) => {
          if (cmd === 'tts_status') return Promise.resolve({installed:true, downloadMb:115});
          if (cmd === 'tts_voices') return Promise.resolve(list);
          return Promise.resolve(null);
        }},
        event: { listen: () => Promise.resolve(() => {}) },
      };
    })();
    """ % json.dumps(ids)

    proc = subprocess.Popen(
        ["/snap/bin/chromium", "--headless=new", f"--remote-debugging-port={dport}",
         "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--remote-allow-origins=*",
         f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws = websocket.create_connection(cdp(dport), timeout=180)
        n = [0]

        def send(method, params=None):
            n[0] += 1
            ws.send(json.dumps({"id": n[0], "method": method, "params": params or {}}))
            while True:
                m = json.loads(ws.recv())
                if m.get("id") == n[0]:
                    if "error" in m:
                        sys.exit(f"{method}: {m['error']}")
                    return m.get("result", {})

        def step(m): print(f"  .. {m}", flush=True)
        step("connected")
        send("Page.enable")
        send("Runtime.enable")
        send("Page.addScriptToEvaluateOnNewDocument", {"source": stub})
        step("navigating")
        send("Page.navigate", {"url": f"http://127.0.0.1:{port}/index.html"})
        step("navigated; settling")
        time.sleep(6)

        def js(expr):
            r = send("Runtime.evaluate",
                     {"expression": expr, "awaitPromise": True, "returnByValue": True})
            if r.get("exceptionDetails"):
                sys.exit(f"page threw: {r['exceptionDetails'].get('text')} {expr[:80]}")
            return r["result"].get("value")

        step("probing page")
        # The hero is a WebGL scene, and under software rendering its animation
        # loop starves everything else. The first version of this script timed
        # out on captureScreenshot and reported an empty menu for one that was
        # drawing fine. Stop the scene before looking at the DOM.
        js("""(() => {
          for (let i = 1; i < 100000; i++) cancelAnimationFrame(i);
          document.querySelectorAll('canvas').forEach(c => c.remove());
          return true;
        })()""")
        # Say what the page thinks, so an empty list is diagnosable instead of
        # just disappointing.
        step("state: " + str(js("""JSON.stringify({
          bridge: !!window.__TAURI__,
          ready: typeof kokoroReady === 'undefined' ? 'undefined' : kokoroReady,
          voices: typeof kokoroVoices === 'undefined' ? 'undefined' : kokoroVoices.length,
          hidden: (document.getElementById('kokoroPicked')||{}).hidden,
        })""")))
        # Put the menu on screen. NOT by clicking whatever looks like Settings —
        # the first version did that, hit the wrong control, and reported an
        # empty list for a menu that was drawing perfectly.
        # Open the sheet the menu actually lives in and switch to its tab. The
        # first version clicked the first control matching /setting/i, hit
        # something else, and measured a 0x0 box.
        js("""(() => {
          // The app is behind the NameOS login gate, so without this the whole
          // interface is display:none and every box measures 0x0 — which is
          // what "the menu is not on screen" meant the first three times.
          const gate = document.getElementById('authGate');
          if (gate) gate.hidden = true;
          const app = document.getElementById('app');
          if (app) { app.hidden = false; app.style.display = ''; }
          document.getElementById('aboutSheet').hidden = false;
          document.getElementById('tabMe').click();
          document.getElementById('kokoroPicked').scrollIntoView({block: 'center'});
          return true;
        })()""")
        time.sleep(0.6)
        step("sheet open on the About me tab")
        time.sleep(1.2)

        SHOTS.mkdir(exist_ok=True)
        counted = js("document.querySelectorAll('#voiceList .voiceRow').length")
        plays = js("document.querySelectorAll('#voiceList .vPlay').length")
        groups = js("[...document.querySelectorAll('#voiceList .voiceGroup')].map(e=>e.textContent)")
        visible = js("""(() => {
          const b = document.getElementById('kokoroPicked');
          if (!b || b.hidden) return null;
          const r = b.getBoundingClientRect();
          return {w: Math.round(r.width), h: Math.round(r.height),
                  top: Math.round(r.top), onScreen: r.width > 40 && r.height > 40};
        })()""")

        print(f"voice rows   : {counted}")
        print(f"play buttons : {plays}")
        print(f"groups       : {groups}")
        print(f"menu box     : {visible}")

        if visible and visible["onScreen"]:
            c = json.loads(js("""(() => {
              const r = document.getElementById('kokoroPicked').getBoundingClientRect();
              return JSON.stringify({x:r.x, y:r.y, width:r.width, height:r.height, scale:2});
            })()"""))
            step("capturing")
            shot = send("Page.captureScreenshot",
                        {"format": "png", "clip": c, "fromSurface": False})
            (SHOTS / "voices-menu.png").write_bytes(base64.b64decode(shot["data"]))
            step("captured")

        bad = []
        if counted != len(ids):
            bad.append(f"{counted} rows drawn for {len(ids)} voices")
        if plays != counted:
            bad.append(f"{plays} play buttons for {counted} rows — every row needs one")
        if not groups:
            bad.append("no accent groups — the list is one undifferentiated run")
        if not (visible and visible["onScreen"]):
            bad.append("the menu is not actually on screen")
        if bad:
            print("FAIL: " + "; ".join(bad))
            return 1
        print("OK — menu drawn, every row has a sample button")
        return 0
    finally:
        proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
