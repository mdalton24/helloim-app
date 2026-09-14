#!/usr/bin/env python3
"""Turn Cyrus's stream script into the two documents Mark actually needs on the night.

He asked for "the script ... on my desktop in word". Vera's review turned that
into two files rather than one, and the reasons are hers:

1. THE SCRIPT. Every spoken block opens with prose that looks identical to the
   block above it, so glancing down mid-type gives him nothing to catch. The
   first four words of every spoken block are therefore BOLD -- that is what the
   eye lands on. And the two things that must not appear on screen go ALONE on
   page one, because they were buried under a nine-bullet checklist, which is
   exactly what a person rushing five minutes before going live scrolls past.

2. THE CUE CARD, printed separately. Beat number, time, first four words, and
   the one must-say line per beat. That page lives on the second monitor; the
   full script is for the night before. Vera called it the cheapest large
   improvement in the whole review.

GENERATED, NEVER HAND-EDITED. Re-run it when the script changes and both files
are correct again. A hand-tidied copy of a generated document is a second source
of truth, and the one that drifts is always the one somebody is reading aloud.

    python3 desktop/make-stream-script-doc.py
"""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Pt, RGBColor, Inches

SRC = Path.home() / "Documents/Cyrus/2026-08-28-learn-stream-script.md"
OUT_SCRIPT = Path.home() / "Documents/JARVIS/desktop/Run-Your-Own-AI-Stream-Script.docx"
OUT_CUE = Path.home() / "Documents/JARVIS/desktop/Run-Your-Own-AI-Cue-Card.docx"

INK = RGBColor(0x11, 0x18, 0x27)
MUTED = RGBColor(0x5B, 0x66, 0x77)
SPOKEN = RGBColor(0x0B, 0x1B, 0x2B)
DIRECTION = RGBColor(0x8A, 0x4B, 0x08)   # stage directions, never spoken
WARN = RGBColor(0xA1, 0x1C, 0x1C)

BEAT = re.compile(r"^## \[(\d+)\]\s+(.*?)\s+—\s+(\d+:\d+)")


def strip_md(s: str) -> str:
    """Markdown emphasis out. He is reading this aloud, not parsing it."""
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*(.+?)\*", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    return s.strip()


def para(doc, text="", size=11, bold=False, color=INK, after=6, before=0,
         italic=False, indent=0.0, align=None, font="Calibri"):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.space_before = Pt(before)
    if indent:
        p.paragraph_format.left_indent = Inches(indent)
    if align is not None:
        p.alignment = align
    if text:
        r = p.add_run(text)
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.color.rgb = color
        r.font.name = font
    return p


def spoken(doc, text: str) -> None:
    """A block he says out loud, with the first four words bold.

    THE BOLD IS THE WHOLE POINT and it is not decoration. Vera: every spoken
    block opens with prose that looks like the block above it, so glancing down
    mid-type gives him nothing to catch. Four words is what the eye lands on.
    """
    words = text.split()
    head, tail = " ".join(words[:4]), " ".join(words[4:])
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.28)
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.line_spacing = 1.25
    r = p.add_run(head + (" " if tail else ""))
    r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = SPOKEN
    r.font.name = "Calibri"
    if tail:
        r2 = p.add_run(tail)
        r2.font.size = Pt(13); r2.font.color.rgb = SPOKEN
        r2.font.name = "Calibri"


def parse(md: str) -> dict:
    """Pull out only what belongs in a document he reads at 3am and on air."""
    lines = md.split("\n")
    out = {"protect": [], "ready": [], "beats": [], "quickref": [], "meta": []}
    section = None
    beat = None

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("# NOTES FOR JARVIS"):
            break                                   # internal, never shipped
        if line.startswith("## Length:"):
            out["meta"].append(strip_md(line[3:])); continue
        if line.startswith("## Two things that must not appear"):
            section = "protect"; continue
        if line.startswith("## Have ready"):
            section = "ready"; continue
        if line.startswith("# QUICK REFERENCE"):
            section = "quickref"; continue
        if line.startswith("# THE SCRIPT"):
            section = "script"; continue

        m = BEAT.match(line)
        if m:
            section = "script"
            beat = {"n": m.group(1), "title": strip_md(m.group(2)),
                    "time": m.group(3), "body": []}
            out["beats"].append(beat)
            continue

        if section == "protect" and line.startswith("- "):
            out["protect"].append(strip_md(line[2:]))
        elif section == "protect" and line.startswith("  ") and out["protect"]:
            out["protect"][-1] += " " + strip_md(line)
        elif section == "ready" and line.startswith("- "):
            out["ready"].append(strip_md(line[2:]))
        elif section == "ready" and line.startswith("  ") and out["ready"]:
            out["ready"][-1] += " " + strip_md(line)
        elif section == "quickref" and line.startswith("|") and "---" not in line:
            cells = [strip_md(c) for c in line.strip("|").split("|")]
            out["quickref"].append(cells)
        elif section == "script" and beat is not None:
            beat["body"].append(line)

    for b in out["beats"]:
        b["blocks"] = blocks_of(b["body"])
    return out


def blocks_of(body: list[str]) -> list[tuple[str, str]]:
    """(kind, text) where kind is 'say', 'screen', 'direction' or 'sub'."""
    blocks, buf, kind = [], [], None

    def flush():
        nonlocal buf, kind
        if buf and kind:
            blocks.append((kind, " ".join(buf).strip()))
        buf, kind = [], None

    for line in body:
        s = line.strip()
        if not s or s == "---":
            flush(); continue
        if s.startswith(">"):
            t = s.lstrip("> ").strip()
            if not t:                       # blank quote line = paragraph break
                flush(); kind = "say"; continue
            if kind != "say":
                flush(); kind = "say"
            buf.append(strip_md(t))
        elif s.startswith("###"):
            flush(); blocks.append(("sub", strip_md(s.lstrip("# "))))
        elif s.startswith("**ON SCREEN:"):
            flush(); blocks.append(("screen", strip_md(s).replace("ON SCREEN:", "").strip()))
        elif s.startswith("|"):
            continue                        # tables live in the quick reference
        else:
            if kind != "direction":
                flush(); kind = "direction"
            buf.append(strip_md(s))
    flush()
    return blocks


def build_script(d: dict) -> None:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"; st.font.size = Pt(11)

    # --- PAGE ONE: the two things, alone. Nothing else may go on this page. ---
    para(doc, "BEFORE YOU GO LIVE", 26, True, WARN, after=4)
    para(doc, "Two things. Nothing else is on this page on purpose.",
         11, False, MUTED, after=26, italic=True)
    for item in d["protect"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(20)
        r = p.add_run("•  ")
        r.font.size = Pt(15); r.font.bold = True; r.font.color.rgb = WARN
        r2 = p.add_run(item)
        r2.font.size = Pt(15); r2.font.color.rgb = INK; r2.font.name = "Calibri"
    para(doc, "Notifications off. Script on the second monitor, never the shared one.",
         13, True, INK, before=18)

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # --- page two onward -----------------------------------------------------
    para(doc, "Run Your Own AI — Episode 1", 22, True, INK, after=2)
    para(doc, "Install Claude Code, then give it a memory. Live, on Windows.",
         12, False, MUTED, after=10)
    for m in d["meta"]:
        para(doc, m, 11, True, INK, after=14)

    if d["ready"]:
        para(doc, "Have ready, or the stream stalls", 15, True, INK, before=8, after=8)
        for item in d["ready"]:
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(5)
            r = p.add_run(item); r.font.size = Pt(11); r.font.color.rgb = INK

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    para(doc, "THE SCRIPT", 20, True, INK, after=2)
    para(doc, "Bold opening words are your cue — that is what to glance at, not the "
              "whole paragraph. Amber lines are directions and are never spoken.",
         10, False, MUTED, after=16, italic=True)

    for b in d["beats"]:
        para(doc, f"[{b['n']}]  {b['title']}", 16, True, INK, before=16, after=1)
        para(doc, b["time"], 11, True, MUTED, after=8)
        for kind, text in b["blocks"]:
            if kind == "say":
                spoken(doc, text)
            elif kind == "screen":
                para(doc, "ON SCREEN — " + text, 10.5, True, DIRECTION, after=8)
            elif kind == "sub":
                para(doc, text, 12, True, INK, before=8, after=4)
            else:
                para(doc, text, 10.5, False, DIRECTION, after=8, italic=True)

    if d["quickref"]:
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        para(doc, "WHERE THIS WILL BREAK", 18, True, WARN, after=3)
        para(doc, "Every row has happened to somebody. None of it ends the stream.",
             10.5, False, MUTED, after=12, italic=True)
        rows = d["quickref"]
        t = doc.add_table(rows=1, cols=3); t.style = "Table Grid"
        for i, h in enumerate(rows[0]):
            c = t.rows[0].cells[i].paragraphs[0].add_run(h)
            c.font.bold = True; c.font.size = Pt(10.5)
        for r in rows[1:]:
            cells = t.add_row().cells
            for i, val in enumerate(r[:3]):
                run = cells[i].paragraphs[0].add_run(val)
                run.font.size = Pt(10.5)

    doc.save(OUT_SCRIPT)


def build_cue(d: dict) -> None:
    """One page for the second monitor. Beat, time, cue, and the must-say line."""
    doc = Document()
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Inches(0.45)
        s.left_margin = s.right_margin = Inches(0.5)
    doc.styles["Normal"].font.name = "Calibri"

    para(doc, "CUE CARD — Episode 1", 17, True, INK, after=1)
    para(doc, "Second monitor. The full script is for the night before, not for now.",
         9.5, False, MUTED, after=10, italic=True)

    t = doc.add_table(rows=1, cols=4); t.style = "Table Grid"
    for i, h in enumerate(["#", "Time", "Your cue — first words", "Must say"]):
        r = t.rows[0].cells[i].paragraphs[0].add_run(h)
        r.font.bold = True; r.font.size = Pt(9.5)

    for b in d["beats"]:
        says = [txt for k, txt in b["blocks"] if k == "say"]
        cue = " ".join(says[0].split()[:5]) + "…" if says else "—"
        # The must-say line is the longest spoken block in the beat: the one
        # carrying the argument, not the handoffs around it.
        must = max(says, key=len) if says else ""
        must = (must[:150] + "…") if len(must) > 150 else must
        cells = t.add_row().cells
        for i, val in enumerate([b["n"], b["time"], cue, must]):
            run = cells[i].paragraphs[0].add_run(val)
            run.font.size = Pt(9)
            if i == 2:
                run.font.bold = True

    para(doc, "If the install finishes early: talk tracks B and C get cut, A never does.",
         10, True, WARN, before=12, after=3)
    para(doc, "If it all falls over: “This is the part where it doesn’t work. Good.”",
         10, True, WARN, after=0)

    doc.save(OUT_CUE)


def main() -> int:
    d = parse(SRC.read_text(encoding="utf-8"))
    build_script(d)
    build_cue(d)
    said = sum(1 for b in d["beats"] for k, _ in b["blocks"] if k == "say")
    words = sum(len(t.split()) for b in d["beats"] for k, t in b["blocks"] if k == "say")
    print(f"beats: {len(d['beats'])}   spoken blocks: {said}   spoken words: {words}")
    print(f"  ~{words/140:.0f} min of talking at 140 wpm")
    print(f"protect items on page one: {len(d['protect'])}  (must be 2)")
    print(f"have-ready items: {len(d['ready'])}   quickref rows: {max(0, len(d['quickref'])-1)}")
    print(OUT_SCRIPT)
    print(OUT_CUE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
