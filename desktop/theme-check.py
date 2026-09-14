#!/usr/bin/env python3
"""The contract every theme must pass before it ships — Iris's spec §1.5.

Pure colour maths, no browser: the token values are typed in below, matching
what index.html's :root and html[data-theme="jarvis"] blocks actually
declare. If either drifts from this file, that is itself worth catching —
this script is meant to be re-run whenever a token changes, not just once.

Checks, all computable, all from §1.5 and §3.1:
  - --text on --bg >= 7:1;  --dim on --panel >= 4.5:1
  - --accent on --bg >= 4.5:1;  --on-accent on --accent >= 4.5:1
  - the accent is >= 30 degrees in hue from --good and from --warn
  - the four frozen status colours reach >= 3:1 on that theme's --panel
  - --idle only ever needs 3:1 (it is a dot, never text)

Run:  python3 theme-check.py
"""
import colorsys
import sys

FROZEN = {"good": "#22c55e", "warn": "#f59e0b", "bad": "#ff7a7a", "idle": "#64748b"}

THEMES = {
    "bella": {
        "bg": "#0b0d10", "panel": "#12161b", "text": "#dfe5ec", "dim": "#7d8894",
        "accent": "#52ffa5", "on-accent": "#06231a",
    },
    "jarvis": {
        "bg": "#000000", "panel": "#08090d", "text": "#e7edf0", "dim": "#a9b0b5",
        "accent": "#8fe6ff", "on-accent": "#03151c",
    },
}


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def relative_luminance(rgb):
    def chan(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(hex_a, hex_b):
    la = relative_luminance(hex_to_rgb(hex_a))
    lb = relative_luminance(hex_to_rgb(hex_b))
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def hue_degrees(hex_c):
    r, g, b = (c / 255 for c in hex_to_rgb(hex_c))
    h, _, _ = colorsys.rgb_to_hls(r, g, b)
    return h * 360


def hue_distance(a, b):
    d = abs(hue_degrees(a) - hue_degrees(b)) % 360
    return min(d, 360 - d)


def main():
    failures = []

    for name, t in THEMES.items():
        print(f"\n== {name} ==")

        checks = [
            ("--text on --bg", t["text"], t["bg"], 7.0),
            ("--dim on --panel", t["dim"], t["panel"], 4.5),
            ("--accent on --bg", t["accent"], t["bg"], 4.5),
            ("--on-accent on --accent", t["on-accent"], t["accent"], 4.5),
        ]
        for label, fg, bg, floor in checks:
            c = contrast(fg, bg)
            ok = c >= floor
            print(f"  {'PASS' if ok else 'FAIL'}  {label}: {c:.2f}:1 (>= {floor}:1)")
            if not ok:
                failures.append(f"{name}: {label} is {c:.2f}:1, needs {floor}:1")

        for status in ("good", "warn"):
            d = hue_distance(t["accent"], FROZEN[status])
            ok = d >= 30
            print(f"  {'PASS' if ok else 'FAIL'}  accent vs --{status} hue distance: {d:.1f}deg (>= 30deg)")
            if not ok:
                failures.append(f"{name}: accent is only {d:.1f}deg from --{status}")

        for status, hexval in FROZEN.items():
            c = contrast(hexval, t["panel"])
            floor = 3.0
            ok = c >= floor
            print(f"  {'PASS' if ok else 'FAIL'}  --{status} on --panel: {c:.2f}:1 (>= {floor}:1)")
            if not ok:
                failures.append(f"{name}: --{status} on --panel is {c:.2f}:1, needs {floor}:1")

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All checks pass.")
    print()
    print("NOT computed here, and still real requirements — verified instead")
    print("by rendering (see shots/theme/):")
    print("  - every rail label fits its box unclipped at 720x520")
    print("  - the rail does not overflow at 720x520")
    print("  - a screenshot of the theme menu OPEN, in each theme, exists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
