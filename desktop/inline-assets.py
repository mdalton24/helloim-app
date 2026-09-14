#!/usr/bin/env python3
"""Fold site/assets/* into site/index.html so the page is genuinely one file.

WHY THIS HAD TO EXIST. The Worker at nameos.ai serves exactly two paths — `/`
and `/index.html` — and answers everything else with a JSON 404 (see
nameos/worker.js, the router at the foot of the file). So every `./assets/...`
reference in the page resolves to a 404 the moment it is live: no brain, no
send-arrow, no asterisk, no photo. Locally it all works, which is precisely the
kind of fault that only shows up in front of the person you were trying to
impress.

Two ways out and this is the cheaper one. Teaching the Worker to serve static
assets means a second source of truth for the same files and a new deploy step;
folding them into the page costs about 190 KB once and means the site has ZERO
external asset requests. The spec asked for a single self-contained index.html
in the first place, so this is the shape it was always meant to have.

  SVGs   -> inlined as data URIs (about 1 KB the pair, and they are markup)
  mesh   -> base64 data URI; fetch() reads a data: URL like any other
  photo  -> re-encoded to WebP at the size it is actually DISPLAYED, then base64

THE PHOTO IS RESIZED, NOT JUST RE-ENCODED, and that is where the saving is. It
ships at 1200x1495 and is drawn into a 27.361vw x 39.722vw box — about 394x572
CSS pixels on a 1440 artboard. Twice that is plenty for a retina screen, and
everything above it is bytes nobody can see.

Idempotent: it skips any reference that is already a data URI, so re-running it
after editing the page is safe.

  inline-assets.py            do it
  inline-assets.py --check    report what would change, touch nothing
"""
import base64
import io
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SITE = HERE / "site"
PAGE = SITE / "index.html"
CHECK = "--check" in sys.argv

# The box the photo is drawn into, at the 1440 artboard, times two for retina.
PHOTO_W, PHOTO_H = 788, 1144
PHOTO_QUALITY = 82


def data_uri(mime, raw):
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def main():
    html = PAGE.read_text()
    before = len(html)
    report = []

    # --- the two SVGs -------------------------------------------------------
    for rel, mime in (("hero/send-icon.svg", "image/svg+xml"),
                      ("sections/asterisk.svg", "image/svg+xml")):
        ref = f"./assets/{rel}"
        if ref not in html:
            report.append(f"  (skip) {rel} — not referenced")
            continue
        raw = (SITE / "assets" / rel).read_bytes()
        html = html.replace(ref, data_uri(mime, raw))
        report.append(f"  {rel}: {len(raw)/1024:.1f} KB inlined")

    # --- the photo ----------------------------------------------------------
    ref = "./assets/sections/financial.png"
    if ref in html:
        from PIL import Image
        im = Image.open(SITE / "assets" / "sections" / "financial.png").convert("RGB")
        orig = im.size
        im.thumbnail((PHOTO_W, PHOTO_H), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=PHOTO_QUALITY, method=6)
        raw = buf.getvalue()
        html = html.replace(ref, data_uri("image/webp", raw))
        report.append(f"  photo: {orig[0]}x{orig[1]} PNG -> {im.size[0]}x{im.size[1]} "
                      f"WebP, {raw and len(raw)/1024:.1f} KB")

    # --- the brain mesh -----------------------------------------------------
    # It is fetched with a template literal, so match the expression rather than
    # a plain string.
    if "${ASSETS}/brain/brain-mesh.bin" in html:
        raw = (SITE / "assets" / "brain" / "brain-mesh.bin").read_bytes()
        uri = data_uri("application/octet-stream", raw)
        html = html.replace("`${ASSETS}/brain/brain-mesh.bin`", "BRAIN_MESH_URI")
        html = html.replace("const ASSETS = './assets';",
                            "const ASSETS = './assets';\n"
                            "/* Inlined by inline-assets.py — the Worker serves only `/`, so an\n"
                            "   ./assets path is a 404 in production. See that script for why. */\n"
                            f"const BRAIN_MESH_URI = '{uri}';")
        report.append(f"  brain mesh: {len(raw)/1024:.1f} KB inlined")

    after = len(html)
    print("\n".join(report) if report else "  nothing to inline (already done?)")
    print(f"page: {before/1024:.0f} KB -> {after/1024:.0f} KB")

    remaining = re.findall(r'["\'`(]\./assets/[^"\'`)]+', html)
    if remaining:
        print("STILL REFERENCING FILES THE WORKER WILL 404:")
        for r in sorted(set(remaining)):
            print("  ", r.lstrip('"\'`('))
        return 1

    if CHECK:
        print("(--check: nothing written)")
        return 0
    PAGE.write_text(html)
    print("written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
