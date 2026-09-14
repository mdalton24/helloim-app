#!/usr/bin/env python3
"""Prove uninstall is reachable from the "already installed" screen again,
but never behind a button whose caption doesn't say what it does.

TWO SCARS, IN ORDER, ARE WHY THIS FILE LOOKS THE WAY IT DOES:

2026-08-31 -- the prompt read "NameOS is already installed" and offered
three buttons captioned only Yes / No / Cancel, with what each one DID
spelled out only in the body text -- [Yes] Repair, [No] Uninstall, [Cancel]
Do nothing. Mark read the headline, not the three lines under it, and
pressed No. It deleted his working install: no install directory, no
registry entry, an empty leftover Program Files folder, the app gone. The
fix that shipped that day removed uninstall from this screen outright --
this file used to assert exactly that (`do_uninstall_label_is_gone`,
`already_installed_prompt_only_offers_repair`).

2026-09-02 -- Mark asked for uninstall back on this screen. Removing the
dangerous option was never the actual fix; the actual fix is that a
destructive action needs a control whose own caption says what it does,
which a native MessageBox cannot give it (Yes/No/Cancel/OK/Retry/Abort/
Ignore is the whole vocabulary, and every one is generic). So the prompt is
now a real `Page custom` (NameOS_AlreadyInstalledPageCreate) built with
nsDialogs: Next stays native and does the safe thing (repair), and a
separate, explicitly-captioned "Uninstall helloim.ai" button -- not the
default control, not reachable by pressing Enter -- leads to a SECOND,
plainly-worded MessageBox that names the action in its own sentence before
anything runs.

This is a STATIC check against the .nsi source, not a run of the compiled
installer -- there is no Windows here to run it on (see Beck's harnesses in
~/Documents/Beck/ for that). What it proves is narrower and cheaper: that
the SHAPE of the 2026-08-31 bug (a button whose visible caption does not
say "uninstall" nonetheless leading somewhere that deletes the install)
cannot exist in the current source, while a genuinely, explicitly-labelled
uninstall path does.

Run it directly:

    python3 ~/Documents/JARVIS/desktop/installer/test-already-installed-prompt.py
"""

import re
import sys
from pathlib import Path

NSI = Path(__file__).with_name("NameOS.nsi")
raw_src = NSI.read_text(encoding="utf-8")

# CODE, WITH FULL-LINE COMMENTS STRIPPED. This file's own comments quote the
# 2026-08-31 bug's exact NSIS shape at length (including the literal string
# "MB_YESNOCANCEL") as history -- checking `raw_src` for that token would
# fail on the comment describing why it must never come back, which is a
# false positive that teaches nobody to trust this test. NSIS line comments
# start with `;` (optionally indented); this does not try to strip trailing
# `; ...` after real code, which none of the checks below need it to.
src = "\n".join(
    line for line in raw_src.splitlines()
    if not line.strip().startswith(";")
)

fails = []
total = [0]


def check(name, condition, why):
    total[0] += 1
    if not condition:
        fails.append("%-48s %s" % (name, why))


DESTRUCTIVE = re.compile(r"RMDir|ExecWait\s+'\"\$R")


def extract_function(name):
    """Return the body of `Function <name> ... FunctionEnd`, or None."""
    m = re.search(r"^Function %s\b" % re.escape(name), src, re.MULTILINE)
    if not m:
        return None
    end = src.find("\nFunctionEnd", m.end())
    if end == -1:
        return None
    return src[m.end():end]


# --- The old escape hatch's NAME must stay gone ----------------------------
#
# `do_uninstall` was both a jump target (`IDNO do_uninstall`) AND a label
# heading ~90 lines that ran the uninstaller, reachable from a bare "No".
# The current fix uses different names throughout (nameos_alreadyinst_*) --
# checking the old name is still absent is cheap insurance against a future
# edit literally copy-pasting the pre-2026-08-31 shape back in.
check("do_uninstall_label_is_gone",
      "do_uninstall" not in src,
      "the old label (or a jump to it) is back in NameOS.nsi")

# --- The three-way MB_YESNOCANCEL shape must not exist ANYWHERE ------------
#
# This is the actual mechanism of the 2026-08-31 bug: a single MessageBox
# with three outcomes and only two visible, generic buttons (Yes/No), so one
# real outcome (Uninstall) had no button of its own and hid behind "No"
# instead. Checked file-wide and unconditionally -- the destructive path no
# longer lives inside one bounded block the way it did when this was a
# single MessageBox, so a block-scoped check would miss a reintroduction
# anywhere else in the file just as easily as it would catch one here.
check("no_three_way_messagebox_anywhere",
      "MB_YESNOCANCEL" not in src,
      "MB_YESNOCANCEL is back in the file -- that is exactly the shape "
      "that let a body-text-only label ('[No] Uninstall') hide behind a "
      "bare Yes/No/Cancel button")

# --- The already-installed page exists, as a real page, not a MessageBox --
check("already_installed_page_is_wired",
      "Page custom NameOS_AlreadyInstalledPageCreate" in src,
      "no `Page custom` wires NameOS_AlreadyInstalledPageCreate into the "
      "wizard -- has the page been unhooked?")

create_fn = extract_function("NameOS_AlreadyInstalledPageCreate")
check("already_installed_page_create_fn_exists", create_fn is not None,
      "could not find Function NameOS_AlreadyInstalledPageCreate ... "
      "FunctionEnd in NameOS.nsi")
create_fn = create_fn or ""

# --- Uninstall is reachable ONLY through a control whose own caption says
# what it does -------------------------------------------------------------
#
# Find the actual button control created on the page and read its literal
# caption text out of the NSD_CreateButton call -- not just "a button
# exists somewhere", but that THIS control's own visible text names the
# action, the property the 2026-08-31 dialog's buttons did not have.
button_match = re.search(
    r'\$\{NSD_CreateButton\}[^\n]*"([^"]*)"', create_fn)
check("uninstall_button_exists_on_the_page", button_match is not None,
      "no ${NSD_CreateButton} call found in NameOS_AlreadyInstalledPageCreate "
      "-- uninstall is not offered as an explicit control on this screen")
button_caption = button_match.group(1) if button_match else ""
check("uninstall_button_caption_names_the_action",
      "uninstall" in button_caption.lower(),
      "the button's own caption is %r -- it does not say 'uninstall', so "
      "clicking it would once again be a generically-labelled control "
      "doing something its text does not describe" % button_caption)

# It must actually be wired to a click handler, not just decorative.
check("uninstall_button_has_a_click_handler",
      "${NSD_OnClick} $0 NameOS_AlreadyInstalledUninstallClick" in create_fn
      or "NameOS_AlreadyInstalledUninstallClick" in create_fn,
      "the uninstall button is created but nothing binds it to "
      "NameOS_AlreadyInstalledUninstallClick")

# --- Nothing destructive is reachable just by loading or showing the page,
# or by taking its default (Next) path -- only by clicking the labelled
# button and then confirming ------------------------------------------------
check("page_create_fn_has_no_removal_call_of_its_own",
      not DESTRUCTIVE.search(create_fn),
      "NameOS_AlreadyInstalledPageCreate itself calls RMDir or runs the "
      "recorded uninstaller -- that would fire just from the page being "
      "shown or from clicking Next, not from a deliberate uninstall click")

# --- The click handler confirms, EXPLICITLY, before anything destructive
# runs ------------------------------------------------------------------
click_fn = extract_function("NameOS_AlreadyInstalledUninstallClick")
check("uninstall_click_handler_exists", click_fn is not None,
      "could not find Function NameOS_AlreadyInstalledUninstallClick ... "
      "FunctionEnd in NameOS.nsi")
click_fn = click_fn or ""

mb_match = re.search(
    r'MessageBox\s+(MB_[A-Z0-9_|]+)[\\\s]*"([^"]*(?:\\\s*\n[^"]*)*)"',
    click_fn)
destructive_match = DESTRUCTIVE.search(click_fn)
check("uninstall_click_handler_has_a_confirm_box", mb_match is not None,
      "no MessageBox found in NameOS_AlreadyInstalledUninstallClick -- "
      "clicking Uninstall would run the uninstaller with no confirmation "
      "at all")
if mb_match:
    check("uninstall_confirm_box_is_not_a_three_way_choice",
          "MB_YESNOCANCEL" not in mb_match.group(1),
          "the confirmation box is MB_YESNOCANCEL -- back to a three-way "
          "generic choice instead of a direct yes/no answer to its own "
          "stated question")
    confirm_text = mb_match.group(2).lower()
    check("uninstall_confirm_box_names_the_action",
          "uninstall" in confirm_text or "remove" in confirm_text,
          "the confirmation box's own text does not say 'uninstall' or "
          "'remove' -- it must name the action in the same sentence the "
          "button answers, not ask a bare, contextless yes/no")
check("uninstall_confirmation_precedes_the_removal_call",
      mb_match is not None and destructive_match is not None
      and mb_match.start() < destructive_match.start(),
      "either there is no destructive call in the click handler, or it "
      "runs before (or without) the confirmation MessageBox")

# --- Belt and suspenders: no OTHER button anywhere in the file maps a bare
# Yes/No/Cancel onto a label that itself removes the install -----------------
#
# Generalises the old block-scoped "only Yes does anything" check to the
# whole file, because the destructive path is no longer confined to one
# bounded MessageBox instruction. For every `MessageBox ... ID<BUTTON>
# <label>` branch anywhere in the script, if the button is No or Cancel --
# the two captions that hid the 2026-08-31 bug -- the label it jumps to must
# not itself run a removal call before its next label or FunctionEnd.
labels = {m.start(): m.group(1)
          for m in re.finditer(r"^\s*([A-Za-z_][A-Za-z0-9_]*):\s*$", src,
                                re.MULTILINE)}
label_starts = sorted(labels)


def label_body(label_name):
    for pos in label_starts:
        if labels[pos] == label_name:
            idx = label_starts.index(pos)
            end = label_starts[idx + 1] if idx + 1 < len(label_starts) else len(src)
            fnend = src.find("FunctionEnd", pos)
            if fnend != -1:
                end = min(end, fnend)
            return src[pos:end]
    return ""


hidden_destructive_buttons = []
for m in re.finditer(r"ID(YES|NO|CANCEL)\s+(\w+)", src):
    button, target = m.group(1), m.group(2)
    if button in ("NO", "CANCEL"):
        body = label_body(target)
        if DESTRUCTIVE.search(body):
            hidden_destructive_buttons.append((button, target))
check("no_generic_no_or_cancel_button_deletes_anything",
      not hidden_destructive_buttons,
      "found button(s) whose caption is the generic %r jumping to a label "
      "that removes the install: %r -- this is the exact 2026-08-31 shape"
      % ([b for b, _ in hidden_destructive_buttons], hidden_destructive_buttons))

if fails:
    print("FAILED %d of %d" % (len(fails), total[0]))
    for f in fails:
        print("  " + f)
    sys.exit(1)
print("test-already-installed-prompt: all %d checks pass" % total[0])
