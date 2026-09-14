#!/usr/bin/env python3
"""Turn Beck's test plan into a sheet Mark can actually open and fill in.

WHY THIS EXISTS. The plan is 1,290 lines of markdown on a Linux box Mark does
not read files on. He asked for "an all feature test sheet", and a sheet is a
thing you scan, sort and tick — not a document you read top to bottom. The
markdown stays the source of truth because it holds the reasoning; this is the
view of it that can be worked through.

IT IS GENERATED, NEVER HAND-MAINTAINED. Two copies of a case list drift, and
the copy that drifts is always the one somebody is filling in. Re-run this
whenever the plan changes and the sheet is correct again by construction.

    python3 desktop/make-test-sheet.py
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

PLAN = Path.home() / "Documents/Beck/2026-08-28-nameos-test-plan.md"
OUT = Path.home() / "Documents/JARVIS/desktop/NameOS-Test-Sheet.xlsx"

# A case opens with "**<n>. <title>**" at the start of a line. The fields that
# follow are labelled, and any of them may be absent or wrap over several lines.
CASE = re.compile(r"^\*\*(\d+)\.\s+(.*?)\*\*\s*$", re.M)
GROUP = re.compile(r"^## (Group \d+ — .*?)\s*$", re.M)
FIELDS = ("Needs", "Drive", "Linux", "Steps", "Expected", "Measure")


def field(body: str, name: str) -> str:
    """One labelled field, unwrapped, or "" if the case does not carry it."""
    others = "|".join(f for f in FIELDS if f != name)
    m = re.search(rf"{name}:\s*(.*?)(?=(?:{others}):|\Z)", body, re.S)
    if not m:
        return ""
    val = m.group(1)
    # Stop at a horizontal rule or a section heading. When a case is the last
    # one before a group break, an absent following field lets the match run to
    # the end of the slice and swallow "--- ## Group 8 — ..." into the measure.
    val = re.split(r"\n\s*---\s*\n|\n##\s", val)[0]
    return re.sub(r"\s+", " ", val).strip().strip(".")


def parse(text: str) -> list[dict]:
    groups = [(m.start(), m.group(1)) for m in GROUP.finditer(text)]

    def group_for(pos: int) -> str:
        name = "—"
        for start, title in groups:
            if start < pos:
                name = title
            else:
                break
        return name

    hits = list(CASE.finditer(text))
    cases = []
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        body = text[m.end():end]
        # A "case" that carries none of the labelled fields is a bold heading
        # that happens to start with a number, not a case. Filtering on shape
        # rather than on position is what keeps this from silently miscounting.
        if not any(field(body, f) for f in FIELDS):
            continue
        case = {
            "n": int(m.group(1)),
            "group": group_for(m.start()),
            "title": m.group(2).rstrip("."),
            **{f: field(body, f) for f in FIELDS},
        }
        # A case already proven on Linux is written in a compressed form —
        # "Linux: ESTABLISHED. Reduced check: ..." — with no separate Measure.
        # That is deliberate: re-running a proven case in full buys the same
        # assurance twice. But a BLANK measure in the sheet reads as an
        # oversight, so lift the reduced check into the column that is actually
        # read. Six cases land here (35, 37, 39, 42, 44, 75) and every one of
        # them would otherwise ship as an empty row.
        if not case["Measure"]:
            reduced = re.search(r"Reduced(?:\s+\w+)?\s+check:\s*(.*)",
                                case["Linux"], re.S)
            if reduced:
                case["Measure"] = ("Reduced check (already proven on Linux) — "
                                   + re.sub(r"\s+", " ", reduced.group(1)).strip())
        # DO NOT INVENT A DRIVE. The first version of this script defaulted a
        # missing Drive to DESKTOP and reported 65 cases as needing a screen
        # when the plan explicitly says DESKTOP for 39 — checked by grepping
        # the plan directly, which is the only reason it was caught. 25 cases
        # carry no Drive line at all, and guessing on their behalf turned a gap
        # in the plan into a confident wrong number in the sheet.
        if not case["Measure"]:
            # Case 75 lands here and it is the one row where a blank would be
            # actively dangerous: it is the recursive-delete guard, and the
            # plan's answer is "read the code, never run it on his machine".
            # A blank measure column invites somebody to invent one.
            case["Measure"] = ("NO MEASURE STATED — read the case in the plan "
                               "before running anything. Some cases are "
                               "deliberately code-read-only.")
        if not case["Drive"]:
            case["Drive"] = "NOT STATED"
        if not case["Needs"]:
            case["Needs"] = "not stated — see plan"
        cases.append(case)
    return cases


def build(cases: list[dict], commit: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Cases"

    headers = ["#", "Group", "What is being tested", "Needs", "Drive",
               "Already proven on Linux", "How it is measured",
               "RESULT", "Evidence / why"]
    ws.append(headers)

    head_fill = PatternFill("solid", fgColor="1F2937")
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.fill = head_fill
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 26

    desktop_fill = PatternFill("solid", fgColor="FEF3C7")   # needs a real screen
    for case in cases:
        ws.append([
            case["n"], case["group"], case["title"], case["Needs"],
            case["Drive"], case["Linux"], case["Measure"],
            "UNRUN", "",
        ])
        r = ws.max_row
        for c in range(1, len(headers) + 1):
            ws.cell(row=r, column=c).alignment = Alignment(
                wrap_text=True, vertical="top")
        # The single most useful thing to see at a glance is which cases cannot
        # run without a desktop, because that is the whole shape of the blocker.
        if "DESKTOP" in case["Drive"].upper() or case["Drive"] == "NOT STATED":
            for c in range(1, len(headers) + 1):
                ws.cell(row=r, column=c).fill = desktop_fill

    # UNRUN is the default on purpose. An unrun check is not a pass, and a sheet
    # that opens with every row blank invites someone to read blank as fine.
    dv = DataValidation(type="list", formula1='"PASS,FAIL,UNRUN,BLOCKED,N/A"',
                        allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(f"H2:H{ws.max_row}")

    widths = [5, 30, 46, 34, 10, 34, 52, 11, 40]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # --- the summary, second so the cases are what opens ----------------------
    s = wb.create_sheet("Summary")
    total = len(cases)
    desktop = sum(1 for c in cases if "DESKTOP" in c["Drive"].upper())
    unstated = sum(1 for c in cases if c["Drive"] == "NOT STATED")
    rows = [
        ("NameOS — all-feature test sheet", ""),
        ("", ""),
        ("Cases", total),
        ("Runnable over SSH alone", total - desktop - unstated),
        ("Need a real desktop session", desktop),
        ("Plan does not say which — treat as needing one", unstated),
        ("", ""),
        ("Plan (the reasoning behind every case)", str(PLAN)),
        ("Generated from commit", commit),
        ("", ""),
        ("RESULT starts at UNRUN for every case, deliberately.", ""),
        ("An unrun check is not a pass. Blank would read as fine.", ""),
        ("", ""),
        ("Amber rows need an interactive logon as jarvis —", ""),
        ("a GUI started over SSH gets no desktop and maps no window.", ""),
    ]
    for a, b in rows:
        s.append([a, b])
    s["A1"].font = Font(bold=True, size=14)
    for r in (3, 4, 5):
        s.cell(row=r, column=1).font = Font(bold=True)
    s.column_dimensions["A"].width = 58
    s.column_dimensions["B"].width = 74

    # Group counts, so the shape of the run is visible without sorting.
    s.append([])
    s.append(["By group", "cases"])
    s.cell(row=s.max_row, column=1).font = Font(bold=True)
    s.cell(row=s.max_row, column=2).font = Font(bold=True)
    seen: dict[str, int] = {}
    for c in cases:
        seen[c["group"]] = seen.get(c["group"], 0) + 1
    for g, n in seen.items():
        s.append([g, n])

    wb.save(OUT)


def main() -> int:
    text = PLAN.read_text(encoding="utf-8")
    cases = parse(text)
    try:
        commit = subprocess.run(
            ["git", "-C", str(Path.home() / "Documents/JARVIS"),
             "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        commit = "unknown"

    build(cases, commit)

    numbers = [c["n"] for c in cases]
    gaps = [n for n in range(1, max(numbers) + 1) if n not in numbers] if numbers else []
    print(f"{len(cases)} cases -> {OUT}")
    print(f"  highest case number: {max(numbers) if numbers else 0}")
    print(f"  needing a desktop:   {sum(1 for c in cases if 'DESKTOP' in c['Drive'].upper())}")
    # A silent gap means the parser dropped a case, and a test sheet that is
    # quietly short is worse than no sheet — it reads as complete.
    print(f"  MISSING NUMBERS:     {gaps if gaps else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
