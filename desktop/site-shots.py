#!/usr/bin/env python3
"""Photograph site/index.html full-page at the widths people actually use.

WHY THIS EXISTS SEPARATELY FROM site-check.py: that one drives the WebGL scroll
scene and photographs each act. This is the marketing page — one document, no
scroll clock — and what matters about it is whether the LAYOUT holds at a
narrow window, not whether a shader compiled.

WHY FULL-PAGE RATHER THAN VIEWPORT: a designer judging hierarchy needs the
whole page in one image. Six viewport crops of a scrolling page hide exactly
the thing being judged, which is what the eye meets first, second and third.

The three widths are not arbitrary. 720 is the app's own minimum window, 1180
is its default from tauri.conf.json -- so the site is judged at the same sizes
as the product it is selling -- and 1600 is a maximised 1080p screen.

Run:  python3 site-shots.py        (writes shots/site/site-*.png)
"""
import base64, http.server, json, socket, socketserver, subprocess, sys
import threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
OUT = HERE / "shots" / "site"
CHROMIUM = "/snap/bin/chromium"

# (label, width, height). Height is the window; the capture is full-page.
WIDTHS = [
    ("min-720", 720, 520),
    ("window-1180", 1180, 800),
    ("max-1600", 1600, 1000),
]


# Iris measured both ends of this on the real page: her hatched failure state
# came out at 6.8 and a real screenshot at 45. The threshold sits well clear of
# both, because the cost of the two errors is not symmetric -- a false alarm
# here sends someone to look at a fine page, while a miss ships a marketing
# site whose screenshots are empty boxes.
FLAT_STDDEV = 15.0
MIN_BOX_PX = 120  # ignore icons and spacers; this is about content images


def flat_images(png_path, boxes, scale=2):
    """Return [(alt, stddev)] for images whose own box is a flat fill."""
    from PIL import Image, ImageStat
    im = Image.open(png_path).convert("L")
    W, H = im.size
    out = []
    for b in boxes:
        if b["w"] < MIN_BOX_PX or b["h"] < MIN_BOX_PX:
            continue
        # Inset 8% so an image's own border or rim light cannot supply the
        # variance that its blank interior is missing.
        dx, dy = b["w"] * 0.08, b["h"] * 0.08
        x0 = int((b["x"] + dx) * scale); y0 = int((b["y"] + dy) * scale)
        x1 = int((b["x"] + b["w"] - dx) * scale); y1 = int((b["y"] + b["h"] - dy) * scale)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(W, x1), min(H, y1)
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        sd = ImageStat.Stat(im.crop((x0, y0, x1, y1))).stddev[0]
        if sd < FLAT_STDDEV:
            out.append((b.get("alt", ""), sd))
    return out


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


def serve(port):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(SITE), **k)
        def log_message(self, *a): pass
    srv = socketserver.TCPServer(("127.0.0.1", port), H)
    srv.allow_reuse_address = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class CDP:
    def __init__(self, port):
        self.port, self.ws, self.n = port, None, 0

    def connect(self):
        # The browser needs a moment to open the debug port; poll rather than
        # sleeping a guessed amount, so a slow box does not fail spuriously.
        for _ in range(80):
            try:
                pages = json.loads(urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json").read())
                page = next(p for p in pages if p["type"] == "page")
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("chromium never opened its debug port")
        from websocket import create_connection  # type: ignore
        self.ws = create_connection(page["webSocketDebuggerUrl"],
                                    suppress_origin=True, timeout=60)

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
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True)
        return r.get("result", {}).get("value")


def main():
    # WHICH PAGE. The site is more than one file now — index.html and
    # connections.html — and a harness that can only photograph the first one
    # quietly means the others never get looked at. Named output, so two pages
    # cannot overwrite each other's shots.
    page = "index.html"
    for a in sys.argv[1:]:
        if not a.startswith("-"):
            page = a if a.endswith(".html") else f"{a}.html"
    stem = page[:-5]
    if not (SITE / page).exists():
        print(f"no such page: {SITE / page}")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    port, dport = free_port(), free_port()
    serve(port)

    proc = subprocess.Popen(
        [CHROMIUM, "--headless=new", f"--remote-debugging-port={dport}",
         "--window-size=1180,800", "--hide-scrollbars",
         "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*",
         "--user-data-dir=/home/mdalton/.cache/nameos-site-shots",
         "--enable-unsafe-swiftshader",
         f"http://127.0.0.1:{port}/{page}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    written, errors = [], []
    try:
        cdp = CDP(dport); cdp.connect()
        cdp.send("Runtime.enable"); cdp.send("Page.enable")

        for label, w, h in WIDTHS:
            # deviceScaleFactor 2 so type is judged at the density a designer
            # actually sees, not a blurry 1x that flatters bad spacing.
            cdp.send("Emulation.setDeviceMetricsOverride",
                     width=w, height=h, deviceScaleFactor=2, mobile=False)
            cdp.send("Page.navigate", url=f"http://127.0.0.1:{port}/{page}")
            time.sleep(2.5)

            # A capture taken mid-transition is indistinguishable from a broken
            # layout, so wait for fonts AND for two animation frames to land.
            cdp.js("document.fonts && document.fonts.ready")
            time.sleep(1.2)

            full = cdp.send("Page.getLayoutMetrics")["cssContentSize"]
            png = cdp.send("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                           clip={"x": 0, "y": 0, "width": w,
                                 "height": full["height"], "scale": 1})["data"]
            p = OUT / f"{stem}--{label}x{h}.png"
            p.write_bytes(base64.b64decode(png))
            written.append((p, w, int(full["height"])))

            # An image that failed to decode is the one failure this page has
            # that looks fine in source and is invisible in a thumbnail.
            #
            # LAZY IMAGES MADE THIS LIE ONCE, AND A CHECK THAT CRIES WOLF IS
            # WORSE THAN NO CHECK. Two of the three shots carry loading="lazy"
            # and sit thousands of pixels below the fold, so the first version
            # of this reported them "failed to load" at all three widths when
            # the page was perfectly fine -- and the byte-level check that
            # disproved it cost more than writing this properly would have.
            #
            # So force every image eager and WAIT for decode before judging.
            # decode() rejects on genuinely corrupt data, which is the failure
            # actually worth catching: a truncated base64 payload from a bad
            # edit to a hand-written file with three of them inlined.
            # LAZY ON A DATA URI IS ALWAYS A BUG, so lint the class rather than
            # catching each instance in a screenshot. The bytes are already in
            # the document and already paid for — there is no request to defer.
            # All it can do is leave the image blank wherever the intersection
            # observer does not run: full-page capture, printing, reader modes,
            # a fast scroll. Iris removed it from index.html on 2026-08-27 and
            # it reappeared on connections.html the same day, which is why this
            # is a build failure and not a comment.
            lazy_inline = cdp.js("""JSON.stringify(Array.from(document.images)
              .filter(i => i.loading === 'lazy' && (i.currentSrc || i.src).startsWith('data:'))
              .map(i => (i.alt || '(no alt)').slice(0, 60)))""")
            for alt in json.loads(lazy_inline or "[]"):
                errors.append(f'{label}: loading="lazy" on an inlined data-URI image '
                              f'— it can only ever blank it ("{alt}…")')

            cdp.js("Array.from(document.images).forEach(i => { i.loading = 'eager'; })")
            broken = cdp.send("Runtime.evaluate", awaitPromise=True, returnByValue=True,
                              expression="Promise.all(Array.from(document.images)"
                                         ".map(i => i.decode().then(() => null)"
                                         ".catch(() => i.currentSrc || i.src)))"
                                         ".then(r => r.filter(Boolean).length)"
                              )["result"]["value"]
            total = cdp.js("document.images.length")
            if broken:
                errors.append(f"{label}: {broken} of {total} image(s) failed to decode")
            else:
                print(f"  ({label}: all {total} images decoded)")

            # AND THEN LOOK AT THE PIXELS, BECAUSE decode() IS NOT PAINT.
            #
            # Iris, 2026-08-27, after this harness gave the page a clean bill:
            # two of the three screenshots were rendering as her diagonal-hatch
            # failure state and this check said "all 3 images decoded." It was
            # right and it was useless. decode() resolves on good BYTES; it says
            # nothing about whether the element painted. loading="lazy" on a
            # data URI is exactly that gap -- the bytes are already in the HTML,
            # so they always decode, and the element can still be blank in a
            # full-page capture where the intersection observer never fires.
            #
            # A real screenshot of a UI has detail everywhere. A flat fill, a
            # hatch, or an empty box does not. So measure variance inside each
            # image's own box in the frame we just captured: below FLAT_STDDEV
            # it is a fill pretending to be content.
            boxes = cdp.js("""JSON.stringify(Array.from(document.images).map(i => {
              const r = i.getBoundingClientRect();
              return { x: r.x + scrollX, y: r.y + scrollY,
                       w: r.width, h: r.height,
                       alt: (i.alt || '').slice(0, 40) };
            }))""")
            flat = flat_images(p, json.loads(boxes), scale=2)
            for alt, sd in flat:
                errors.append(f"{label}: an image is not painting — "
                              f"stddev {sd:.1f} inside its box (\"{alt}…\")")
            if not flat:
                print(f"  ({label}: all {total} images carry real detail)")

    finally:
        proc.terminate()
        try: proc.wait(timeout=10)
        except Exception: proc.kill()

    for p, w, hh in written:
        print(f"  {p.name}  ({w}x{hh} css px, full page)")
    print(f"\n{len(written)} shots -> {OUT}")

    if errors:
        print("\nFAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nOK — every image decoded at every width.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
