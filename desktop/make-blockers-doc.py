#!/usr/bin/env python3
"""The Word document Mark asked for: what I need in order to finish testing.

Mark, 2026-08-28: "If there are things you can't test, create a word document on
my windows profile telling me what you need to test it and we will make it so."

WRITTEN AS THINGS HE CAN DO, NOT AS OBSTACLES. Every item says what is blocked,
how many cases it unlocks, and the single action that unblocks it. He asked what
we NEED, so the answer is an ask, not an explanation of why we are stuck.

Ordered by what it unlocks. One item is worth more than the other six together
and it is first, because a list read top-down should spend his attention in the
right order.

    python3 desktop/make-blockers-doc.py
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

OUT = Path.home() / "Documents/JARVIS/desktop/NameOS-What-I-Need.docx"

INK = RGBColor(0x11, 0x18, 0x27)
MUTED = RGBColor(0x5B, 0x66, 0x77)
ACCENT = RGBColor(0x0B, 0x6B, 0x5B)
BAD = RGBColor(0xA1, 0x1C, 0x1C)

# (ask, unlocks, what is blocked, what to do)
ASKS = [
    ("A NameOS account I can sign in with",
     "about 40 of the 78 cases",
     "The app stops at the sign-in gate, exactly as designed — that behaviour "
     "is itself one of the cases that passed. Everything behind it is "
     "untested: the whole six-question setup, naming, the roaming persona, "
     "folder trust, About me, connectors, skills, the tour, and the Escape "
     "defect that was fixed today.",
     "One working account on nameos.ai I can use, or your say-so to create a "
     "test one. Password reset is currently broken, so it has to be an "
     "account that already works."),

    ("A throwaway Windows machine or virtual machine",
     "four cases, including the two most dangerous ones",
     "Four checks cannot safely run on a computer you work on. One upgrades "
     "from an older machine-wide install. One is a genuinely clean uninstall. "
     "One deliberately breaks the web component NameOS runs on, which other "
     "software on your machine also uses. One tests the guard that stops the "
     "uninstaller deleting from the root of a drive.",
     "Any disposable Windows machine — a spare box, or a virtual machine I "
     "can reach. I will not run these on your daily driver under any "
     "circumstances."),

    ("Permission to run the uninstaller",
     "five cases",
     "Uninstalling is the one thing I deliberately did not do. NameOS is "
     "currently still installed under the jarvis profile, and taking it off "
     "is the only way to test that it removes itself cleanly and leaves "
     "nothing behind.",
     "Either your go-ahead to run it under the jarvis profile only, or the "
     "throwaway machine above — which covers this and is the safer answer."),

    ("What the licence agreement should actually say",
     "one case, and it is a legal one, not a technical one",
     "The installer shows a page headed \"License Agreement\" with the "
     "sentence \"You must accept the agreement to install NameOS.\" What it "
     "shows is 72 bytes of marketing tagline. There is no agreement there. "
     "Every customer is being asked to accept nothing.",
     "Tell me what it should say, or say you want a standard one drafted for "
     "you to approve. This is not something I should write on my own."),

    ("Confirm the publisher name",
     "shown to every customer, in Add or Remove Programs",
     "The installer registers the publisher as \"vDesktop, LLC\". I have no "
     "way to confirm that is the name you want on it.",
     "Confirm it, or tell me the right one."),

    ("Real credentials for a connector or two",
     "three cases",
     "Connecting the app to an outside service can only be tested with a real "
     "key. I will not invent one, and a fake key proves the error path only.",
     "One low-value key for any service you already use, or a test account. "
     "It gets stored encrypted and never written into a note."),

    ("A second, older build to update from",
     "two cases, one of them the most security-sensitive untested line in the "
     "product",
     "The updater has never been run. Testing it needs a genuinely older "
     "build installed first, then an update to a newer one. One of these "
     "checks covers whether the app will accept an update it should refuse.",
     "Nothing from you if you are happy for me to build and keep an older "
     "version deliberately. Say the word and I will."),

    ("A microphone, and sound out",
     "seven cases",
     "Voice input and voice output are the largest genuinely Windows-only "
     "part of the product — the microphone does not exist at all on Linux, so "
     "none of it has ever been exercised. The test machine has no microphone "
     "I can use and no way for me to hear what comes out.",
     "Tell me whether that box has a microphone and speakers. If it does, I "
     "can drive them; if not, this waits for the throwaway machine or for you "
     "to run those seven by hand."),
]


def line(doc, text, size=11, bold=False, color=INK, space_after=6,
         italic=False, align=None):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    r.font.name = "Calibri"
    return p


def main() -> int:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)

    line(doc, "NameOS — what I need from you to finish testing", 20, True, INK, 2)
    line(doc, "28 August 2026", 10, False, MUTED, 14)

    line(doc,
         "The test plan is 78 cases covering every feature. 19 have passed, "
         "2 failed, and 57 are waiting on one of the things below. Nothing "
         "here is a problem with the product — it is the list of doors I "
         "cannot open on my own.",
         11, False, INK, 8)
    line(doc,
         "The first item unlocks more than the other seven put together. If "
         "you only do one thing, do that one.",
         11, True, ACCENT, 16)

    line(doc, "What I am asking for", 15, True, INK, 10)

    for i, (ask, unlocks, blocked, todo) in enumerate(ASKS, start=1):
        line(doc, f"{i}.  {ask}", 13, True, INK, 2)
        line(doc, f"Unlocks {unlocks}.", 10, False, ACCENT, 6, italic=True)
        line(doc, blocked, 11, False, INK, 4)
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(16)
        p.paragraph_format.space_before = Pt(0)
        r = p.add_run("What would unblock it:  ")
        r.font.bold = True
        r.font.size = Pt(11)
        r.font.color.rgb = INK
        r2 = p.add_run(todo)
        r2.font.size = Pt(11)
        r2.font.color.rgb = INK

    doc.add_page_break()

    line(doc, "Two things that are already broken", 15, True, BAD, 4)
    line(doc,
         "These are not blocked. They are found, and they are being fixed. "
         "Listed so you hear them from me rather than finding them yourself.",
         10, False, MUTED, 12, italic=True)

    line(doc, "The last screen of the installer has invisible text.", 12, True, INK, 2)
    line(doc,
         "The \"Launch NameOS now\" tick box on the Finish page is drawn in "
         "black on a near-black background. It is there, it works, and it "
         "cannot be read — so anyone wanting to untick it cannot tell what it "
         "does. Every automated check passed on it; it was caught only by "
         "looking at a picture. Being fixed now.",
         11, False, INK, 12)

    line(doc, "The licence page shows a slogan, not a licence.", 12, True, INK, 2)
    line(doc,
         "Covered as item 4 above, because the fix is a decision from you "
         "rather than a change I should make.",
         11, False, INK, 16)

    line(doc, "What I can now do without asking", 15, True, INK, 6)
    line(doc,
         "Since this morning I can sign in to that machine, install and run "
         "NameOS under the jarvis profile, drive the installer and the app, "
         "and photograph any window to see what a customer would actually "
         "see. Your own session is never touched and the machine is never "
         "restarted.",
         11, False, INK, 12)
    line(doc,
         "Two things I asked for earlier turned out not to be needed after "
         "all, so I am withdrawing them: permission to install an automation "
         "tool, and removing the copy of NameOS that was on the machine. "
         "Neither is required.",
         11, False, MUTED, 6, italic=True)

    doc.save(OUT)
    print(f"{len(ASKS)} asks -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
