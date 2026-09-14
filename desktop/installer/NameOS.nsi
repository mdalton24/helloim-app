; helloim.ai Windows installer — a real setup wizard (Welcome, Next, Install, Finish),
; the thing that competes with Zoey's setup. Compiled with makensis on Linux.
Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"   ; ${GetParent}, used by the uninstaller
!include "WinMessages.nsh"  ; ${WM_SETTEXT} etc, used by the talking install page below

; DISPLAY NAME -- REVERTED 2026-09-05 (Mason, per Beck's NO-GO). A 2026-09-04
; comment here tried to make the user-visible brand "Hai" while leaving every
; on-disk name (the `helloim.ai.exe` filename, IDENT, the site) as
; "helloim.ai" -- but nobody actually finished that rename: the wizard
; strings below (Welcome/Finish page text, the already-installed and
; uninstall dialogs, the step captions) were left hardcoded to the literal
; word "Hai" instead of pointing at this constant, so the label and the code
; would have drifted the moment either one changed again. Mark's word today
; is that the app "should continue to say Helloimai just as before" -- so
; every user-visible wizard string below is ${APP}, and "Hai" survives
; nowhere but the tile icon art. See IDENT's own comment two lines down for
; the separate distinction it draws: this constant is the display label,
; IDENT is the thing every already-installed machine's settings are keyed on,
; and the two must never be conflated.
!define APP "helloim.ai"
!define COMPANY "vDesktop, LLC"
; Passed in by ship-windows.sh with -DVERSION= so there is ONE version number in
; the product, read from tauri.conf.json. It used to be typed here as well, and a
; second copy of a version is a copy that goes stale -- an installer registering
; 0.1.0 in Add/Remove Programs for a 0.2.0 build makes the updater offer people
; a version they already have, forever.
!ifndef VERSION
  !define VERSION "0.0.0-dev"
!endif
; Must match `identifier` in tauri.conf.json -- it IS the settings folder name.
;
; LEFT AS "ai.nameos.desktop" DELIBERATELY IN THE helloim.ai RENAME, 2026-09-02.
; ${APP} is the display name and changes freely; IDENT is the thing every
; already-installed machine's settings, memory, credentials and log path are
; keyed on (see startup.rs::IDENTIFIER and the ConfigDir written below). This
; is a rename of what the product is CALLED, not a migration of what it IS on
; disk -- changing this too would silently start a fresh, empty settings
; folder for anyone already running the app, and there is no coordinated
; migration for that today. Flagged for Mark/Beck/Vance rather than guessed at.
!define IDENT "ai.nameos.desktop"

Name "${APP}"
OutFile "helloim.ai-Setup.exe"
; PER-USER, SO WINDOWS NEVER ASKS — Mark, 2026-08-27: "don't ask for all
; those permissions just put them in play."
;
; Writing to Program Files REQUIRES administrator, and requiring administrator
; is what makes Windows throw the UAC prompt. There is no flag that keeps one
; and drops the other; the only way to stop being asked is to stop needing it.
; So helloim.ai installs into the user's own Programs folder, which is exactly
; where Windows expects an app that installs itself to go.
;
; WHAT THIS TRADES. It installs for the person who ran it rather than for
; every account on the PC — right for a personal assistant, and the reason
; every registry write below moves from HKLM to HKCU with it. A mismatch
; there is the classic per-user-installer bug: the app lands in the user hive
; and Add/Remove Programs looks in the machine hive, so it installs fine and
; cannot be uninstalled.
InstallDir "$LOCALAPPDATA\Programs\${APP}"
InstallDirRegKey HKCU "Software\${APP}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "${APP} ${VERSION}"

; THE INSTALL PAGE TALKS INSTEAD OF LOGGING FILENAMES -- Mark, 2026-08-29,
; reversing an earlier decision of his own: "I want the openjarvis setup but
; make it look slightly different... as it is installing talking about our os
; and top features while loading." The reference is OpenJarvis's own setup
; screen (frontend/src/components/SetupScreen.tsx) -- a vertical list of named
; steps, each with a live detail line, in one of three states: done, active
; with a spinner, waiting. Same idea, our execution: a helloim.ai step list instead
; of theirs, our own wording, no arc-reactor mark, no borrowed palette.
;
; "nevershow" hides the raw file log and the "Show details" toggle for good --
; the thing this whole change exists to remove was a person watching filenames
; scroll past that mean nothing to them. It also frees the vertical space the
; step list and the rotating caption below actually use; without it the log
; listbox sits on top of anything drawn in that area and nothing painted there
; is visible at all -- proven by trying it the other way first, see the note on
; NameOS_InstFilesShow.
ShowInstDetails nevershow

!define MUI_ABORTWARNING

; THE INSTALLER LOOKS LIKE THE APP — Mark, 2026-08-27: "can you pretty up the
; installer with some humor on the steps and to match the current theme".
;
; Taken from the app's own sign-in screen rather than picked by eye: near-black
; ground, off-white text, and the mint the Sign in button uses. NSIS wants
; RRGGBB with no hash. MUI_BGCOLOR governs the Welcome and Finish pages, which
; are the two full-bleed ones and therefore the two that look wrong in default
; battleship grey next to a black app.
;
; AND IT WAS THE WRONG THEME'S BLACK — corrected 2026-08-29. `0B0D10` is
; BELLA's --bg, and the app defaults to JARVIS (`DEFAULT_THEME_ID` in
; ui/index.html, set 2026-08-28 on Mark's "Default the profile to Jarvis with
; your voice"). So the installer spent a day previewing a theme the first
; launch would not show: install on Bella's near-black, land on Jarvis's true
; black and cyan. These four values are Jarvis's own --bg, --text and --accent,
; copied from the token block in ui/index.html; if that theme's tokens move,
; move these. Anything that reads "which theme does a new machine get" has to
; answer the same in both files or the seam is visible in the first ten seconds
; of owning the product.
!define MUI_BGCOLOR "000000"
!define MUI_TEXTCOLOR "E7EDF0"
!define NAMEOS_ACCENT "8FE6FF"
; THE PROGRESS BAR'S TROUGH -- Beck's real-hardware finding, 2026-08-29: the
; trough was set to the panel's own black (see NameOS_InstFilesShow, the
; PBM_SETBKCOLOR call), so from 0% until the fill catches up the bar is a
; black rectangle on a black panel. Measured on a real install: zero
; non-background pixels in the bar row at 2s and at 5s, 436 of 503 in accent
; by 9s -- it reads as hung, not as started. The old stock bar was ugly and
; its grey trough was always visible; this loses that property along with the
; ugliness. Not a theme token -- neither --panel (#08090d) nor --bg (#000000)
; reads as distinct from the panel behind it, and --line is a translucent
; overlay with no flat equivalent to borrow. A plain elevated-surface grey,
; clearly above black without competing with the accent fill once it arrives.
!define NAMEOS_TROUGH "33383D"

; THE ARTWORK IS THE APP, PHOTOGRAPHED — Mark, 2026-08-29: asked whether the
; installer could "look similiar to that", and when asked which, "Yes like
; nameos".
;
; branding/welcome.bmp and branding/header.bmp are not illustrations of the
; product, they are CROPS OF IT: a real render of the Jarvis board scene taken
; from ui/index.html at 1440x900, the one geometry that scene is proven to look
; right at. Regenerate them with make-installer-art.py, never by hand — the
; crop is chosen by a density sweep rather than by eye, because the first one
; picked by eye was a third emptier and read as a black rectangle.
;
; 164x314 and 150x57 are MUI2's own slot sizes and are not negotiable; both are
; cut at exactly those ratios so nothing is stretched. A stretched circuit
; field looks like a compression artifact, which is the one thing a first
; impression cannot afford.
!define MUI_ICON "..\src-tauri\icons\icon.ico"
!define MUI_UNICON "..\src-tauri\icons\icon.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "branding\welcome.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "branding\welcome.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "branding\header.bmp"
!define MUI_HEADERIMAGE_UNBITMAP "branding\header.bmp"

!define MUI_WELCOMEPAGE_TITLE "Welcome to ${APP}"
; "your own" appeared twice in one sentence -- caught in independent review,
; 2026-08-29. Dropped the second one rather than the first: "your own AI
; team" is the part worth keeping, it is the whole pitch; "on your own
; machine" says the same thing about the machine that "your computer" three
; words earlier already said.
!define MUI_WELCOMEPAGE_TEXT "This will install ${APP} on your computer — your own AI team, running on your machine.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN "$INSTDIR\helloim.ai.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${APP} now"

; THE "LAUNCH NAMEOS NOW" LABEL WAS INVISIBLE — Beck, 2026-08-28, case 5. She
; found it by looking at a screenshot of the Finish page; every automated
; check passed, because the checkbox itself is fine — checked, named, clickable,
; Finish genuinely launches the app. Only the TEXT NEXT TO IT was black on our
; near-black background, measured at ~1.05:1 contrast against a 4.5:1 floor.
; It is the last screen every customer sees.
;
; NOT A TYPO. Confirmed by reading Finish.nsh out of the nsis 3.10 package
; actually installed on this box, not from memory: MUI_TEXTCOLOR reaches every
; Static control on this page (the title, the body text) via a plain
; SetCtlColors call, and it is applied to the Run checkbox exactly the same
; way -- and then silently overridden. Windows draws a themed checkbox's label
; itself and ignores SetCtlColors' text colour for it; this is NSIS's own
; long-standing issue, and their source names it outright: "SetCtlColors does
; not change the check/radio text color (bug #443)".
; https://sourceforge.net/p/nsis/bugs/443/
;
; NSIS CARRIES ITS OWN FIX FOR THIS AND IT WAS TRIED FIRST, AND REJECTED AFTER
; BEING RUN, NOT AFTER BEING READ. `MUI_FORCECLASSICCONTROLS` makes NSIS call
; UXTHEME::SetWindowTheme with an empty theme name on the Run checkbox, which
; is the exact call the source uses for Windows' own high-contrast mode. It
; DOES fix the checkbox's text. It also, measured on a real build run end to
; end on Mark's own second machine (10.0.0.51), throws away the near-black
; page underneath it: the title, the body text and the panel background all
; reverted to the stock white MUI theme, on THIS page only. Screenshotted A/B
; against a build compiled from the exact prior commit with nothing else
; changed -- the unmodified build reproduces Beck's bug exactly (dark page,
; invisible label); the classic-controls build "fixes" the label onto a page
; that no longer looks like helloim.ai. That trade is worse than the bug: a
; correct dark theme with one unreadable line beats an unbranded page. This is
; the "different ugly" the brief warned about, so it does not ship.
;
; THE FIX THAT SHIPPED DID NOT TOUCH THE CHECKBOX, AND THAT ASSUMPTION BROKE
; UNDER WINE -- corrected 2026-08-29, found from a screenshot Jarvis looked at
; himself. The plan above was: leave $mui.FinishPage.Run's own text exactly as
; MUI2 builds it, on the theory that bug #443 makes it invisible regardless,
; and lay a second, readable Static label over the same space so a sighted
; person sees exactly one line. That theory was checked on real hardware
; (Mark's second machine, 10.0.0.51) and held there. It does NOT hold under
; Wine: Wine's theme engine does not reproduce bug #443, so the checkbox's own
; text renders VISIBLY there, stacked directly against the added label --
; "Launch helloim.ai now" printed twice, one above the other, on the one screen
; every customer sees last. Whether that is only a Wine artifact or also true
; on some real Windows builds was not something worth staking the page on.
;
; THE FIX NOW BLANKS THE CHECKBOX'S OWN TEXT, on every platform, so there is
; structurally only one string that can ever be visible -- see the
; ${NSD_SetText} call in NameOS_FinishPageShow below. This trades away the
; accessibility property the old comment cared about: a screen reader asking
; the checkbox for its own accessible name now gets nothing, because the name
; and the visible label were the same string. A real fix keeps both by setting
; the accessible name a different way (an explicit MSAA/UIA name, independent
; of WM_GETTEXT) -- that is follow-up work, not done here, said plainly rather
; than silently dropped.
;
; Copied into our own name for the same reason as the position numbers below:
; MUI_UNSET clears MUI_FINISHPAGE_RUN_TEXT itself the moment the page macro
; below finishes expanding (Finish.nsh line 191), so by the time our function
; is compiled it would already be gone. The first build of this fix left the
; reference as ${MUI_FINISHPAGE_RUN_TEXT} and makensis warned "unknown
; variable/constant... ignoring" and silently compiled the literal seven
; characters "{MUI_FINISHPAGE_RUN_TEXT}" onto the label instead of the real
; text -- caught by reading the compiler's own warning, not by running it.
!define NAMEOS_FINISHRUN_LABEL_TEXT "${MUI_FINISHPAGE_RUN_TEXT}"

; UNINSTALL IS BACK ON THE ALREADY-INSTALLED SCREEN, AND THIS TIME THE
; DESTRUCTIVE ACTION HAS ITS OWN BUTTON -- Mark asked for it back 2026-09-02.
; See Function .onInit, below, for the 2026-08-31 history: a three-way
; MB_YESNOCANCEL where [No] silently meant "delete the install", spelled out
; only in body text nobody reads under a headline that already sounds like
; the safe answer -- Mark read "already installed", pressed a button, lost
; his working install. The fix that shipped that day removed uninstall from
; this screen outright, because native MessageBox has no way to relabel its
; own buttons: Yes/No/Cancel/OK/Retry/Abort/Ignore is the entire fixed
; vocabulary, and every one of them is generic by construction. A generic
; caption is exactly what let a consequential choice hide behind an
; unrelated word.
;
; SO THIS IS A REAL PAGE, NOT A MessageBox -- the only way to put an actual
; verb on a button is a real control, which means a real dialog. `Page
; custom`, built with nsDialogs, in the one context this file has already
; proven that plugin needs: a page nsDialogs itself creates via its own
; ::Create call, not an arbitrary point mid-script (see the InstFiles-page
; caution further down, where the identical calls silently do nothing).
;
; NEXT STAYS NATIVE AND UNRELABELLED. It is not hiding anything: the page's
; own body text, immediately above it, says in plain words what clicking it
; does (repair / update), the same way the Welcome page one screen later
; already says "Click Next to continue" without that ever reading as
; ambiguous. Renaming its caption would mean driving WM_SETTEXT against a
; wizard-chrome control this file has not proven safe to touch, for a
; cosmetic gain this fix does not need.
;
; UNINSTALL GETS ITS OWN, SEPARATE, EXPLICITLY-CAPTIONED BUTTON, apart from
; the page's normal flow -- not the control with default focus (Next has
; that), not reachable by pressing Enter. Clicking it does not itself remove
; anything: NameOS_AlreadyInstalledUninstallClick, below Function .onInit,
; asks a SECOND, plainly-worded question -- one that names the action in the
; same sentence the button answers -- before anything on disk is touched.
; installer/test-already-installed-prompt.py checks both halves: that the
; MB_YESNOCANCEL shape is gone from the whole file, not just one block, and
; that no button anywhere maps a bare Yes/No/Cancel onto a destructive label.
Page custom NameOS_AlreadyInstalledPageCreate

!insertmacro MUI_PAGE_WELCOME

; THE LICENSE PAGE IS GONE -- an independent review caught this, 2026-08-29,
; and it predates every pass in this file's own history above. `LICENSE.txt`
; was 72 bytes: the product name, the tagline, and "This installs helloim.ai on
; your PC." Not terms -- marketing copy, sitting under a page that says
; "Please review the license terms", "Press Page Down to see the rest of the
; agreement", and "You must accept the agreement to install helloim.ai", in front
; of an "I Agree" button a paying customer has to press to continue. That is
; not a placeholder that happens to be harmless -- it is asking someone's
; legal assent to an agreement that is not there.
;
; NO LICENSE WAS WRITTEN TO REPLACE IT. Real terms are Mark's decision, not
; this file's, and it is his to make separately. An installer with no license
; page at all is completely ordinary -- most are exactly that -- so removing
; the page is a real fix on its own, not a placeholder for a future one.
;
; `LICENSE.txt` STAYS ON DISK, deliberately, just unreferenced by the wizard.
; Deleting it risks breaking something else that expects the file to exist
; (ship-windows.sh, a stray reference elsewhere); leaving it costs nothing,
; since nothing in the compiled installer points at it anymore.
;
; THE DIRECTORY PAGE IS GONE TOO -- Mark's report, 2026-09-04: "I was asked to
; pick a folder after setting up brain and then again on step 10 of the
; installer." Two different prompts, both asking to "pick a folder", back to
; back in one flow: this page asks where to put the PROGRAM FILES; the app's
; own first-run wizard (`main.rs::pick_folder`, "Which folder should it work
; in?") asks which folder the AI should treat as its trusted working
; directory. Those are genuinely different questions, but a person who has
; just answered one has no reason to expect a second, and the folder-trust
; pick is the one that actually matters -- it is a security decision
; (`folder_trust.rs`'s whole module), not a place-to-put-files one.
;
; AND THIS PAGE HAD NO REASON TO EXIST HERE IN THE FIRST PLACE. `InstallDir`
; above already fixes the install location at `$LOCALAPPDATA\Programs\${APP}`,
; a per-user path chosen so Windows never has to ask for elevation -- see that
; declaration's own comment, Mark's words verbatim: "don't ask for all those
; permissions just put them in play." Asking where to install, right below a
; comment explaining why this installer is built to not ask people things, was
; the same mistake in a different spot. `InstallDirRegKey` above still seeds
; $INSTDIR with whatever a previous install used (or the default, on a first
; run); removing the page only removes the question, not the value.
;!insertmacro MUI_PAGE_DIRECTORY

; NSD_CreateLabel AND NSD_CreateTimer DO NOT WORK ON THIS PAGE, AND THAT IS NOT
; A GUESS -- built and run under wine three times before writing a line of
; this. nsDialogs keeps exactly one dialog handle (g_dialog.hwDialog) and only
; ever sets it inside nsDialogs::Create; the Welcome/License/Directory/Finish
; pages MUI2 builds ARE nsDialogs pages (Finish.nsh calls nsDialogs::Create
; itself, which is why NameOS_FinishPageShow's ${NSD_CreateLabel} below works),
; but InstFiles is the old, non-nsDialogs page -- the same one every classic
; NSIS installer has always used, built from a fixed dialog template compiled
; into modern.exe. Called from here, ${NSD_CreateLabel} silently creates a
; window parented to nothing that never appears, and ${NSD_CreateTimer} never
; fires -- reproduced with a screenshot showing nothing where the label should
; be, both effects gone the moment the same calls run on the Finish page.
;
; A REAL WINDOWS TIMER WAS THE FIRST THING TRIED AFTER THAT, VIA THE RAW WIN32
; SetTimer call rather than nsDialogs, and it was ALSO rejected -- not because
; it failed, but because it could not be proven safe. The callback has to be a
; native stdcall TIMERPROC, and the only way to hand NSIS script code to native
; code as a callback is GetFunctionAddress, whose stack-marshaling contract for
; an arbitrary Win32 callback (as opposed to Call/Goto, its documented uses) is
; not written down anywhere findable, in NSIS's own docs or its forums. The
; System plugin has its own documented callback mechanism (System::Get, the 'k'
; type) and its own docs say plainly it "can only be called while calling
; another function" -- it is built for synchronous callbacks like EnumWindows,
; not an independently-ticking timer. Getting a native callback ABI wrong does
; not fail loudly in testing; it corrupts a stack in a way that can render
; differently on a real machine than under Wine. That is not a place to guess.
;
; SO THE ROTATION IS TIED TO REAL PROGRESS, NOT A CLOCK. Four plain controls
; are created below with ordinary, fully-documented calls -- CreateWindowEx
; once at Show, SendMessage/WM_SETTEXT from the Section as each real step
; actually finishes. Slower on a very fast machine than a smooth timer would
; be, and it is never wrong about what step helloim.ai is actually on, which a
; wall-clock rotation already picked at random would not be able to promise.
!define MUI_PAGE_CUSTOMFUNCTION_SHOW NameOS_InstFilesShow
!insertmacro MUI_PAGE_INSTFILES

; The step text, plain compile-time strings rather than LangStrings -- there is
; one language here (MUI_LANGUAGE "English", below) and a LangString table adds
; a runtime lookup this page does not need. WAIT/ACTIVE per step: created
; showing WAIT (or ACTIVE for the first, since work starts the moment this page
; is shown, not on a later click), then swapped to ACTIVE/DONE by SendMessage
; from the Section as each real step actually happens -- see the four
; checkpoints in Section "helloim.ai" below. DONE reuses the ACTIVE glyph text and
; is told apart by COLOUR alone (accent instead of ink) -- see the marker note.
;
; HOLLOW/FILLED CIRCLE, NOT ASCII ARROWS -- corrected 2026-08-29 after Jarvis
; looked at the page and called the o/->/v markers placeholder characters. The
; real glyphs (U+25CB hollow circle, U+25CF filled circle, U+2713 check) were
; tried FIRST and two of three tofu-boxed under this box's wine test: Wine's
; GDI font-linking does not fall through to a symbol font for a codepoint the
; primary font does not cover, even though Noto Sans Symbols/Symbols2 ARE
; installed here at the fontconfig level -- verified with a throwaway probe
; page that put a dozen candidate glyphs on screen at once and screenshotted
; which ones painted. Requesting the font family "Segoe UI Symbol" directly
; (CreateFontIndirect, not WM_GETFONT-borrowed) fixed the circles -- fc-match
; substitutes something with real coverage when asked by that name outright,
; where automatic linking from a non-symbol logical font does not reach it --
; and the SAME font renders the plain Latin label text beside it without
; trouble, so one font serves the whole row. The check mark stayed tofu even
; asked for by name, so DONE is a filled circle in the accent colour rather
; than a checkmark -- a real gap against a literal checklist, said plainly.
; On real Windows, Segoe UI itself carries these Unicode blocks and dedicated
; linking to Segoe UI Symbol is unlikely to even be needed -- but nothing here
; ships on the strength of "likely"; this is what was proven in front of a
; screenshot, and it is a legitimate, deliberate step-state language on its
; own terms: hollow for waiting, filled for under way, filled-in-accent once
; genuinely done.
!define NAMEOS_GLYPH_WAIT  "○"
!define NAMEOS_GLYPH_GO    "●"
!define NAMEOS_STEP1_WAIT   "${NAMEOS_GLYPH_WAIT}   Setting up ${APP}"
!define NAMEOS_STEP1_ACTIVE "${NAMEOS_GLYPH_GO}   Setting up ${APP}"
!define NAMEOS_STEP2_WAIT   "${NAMEOS_GLYPH_WAIT}   Adding your voice"
!define NAMEOS_STEP2_ACTIVE "${NAMEOS_GLYPH_GO}   Adding your voice"
!define NAMEOS_STEP3_WAIT   "${NAMEOS_GLYPH_WAIT}   Checking your system"
!define NAMEOS_STEP3_ACTIVE "${NAMEOS_GLYPH_GO}   Checking your system"
!define NAMEOS_STEP4_WAIT   "${NAMEOS_GLYPH_WAIT}   Finishing up"
!define NAMEOS_STEP4_ACTIVE "${NAMEOS_GLYPH_GO}   Finishing up"

; The three row colours, off the SAME Jarvis theme tokens the rest of the
; installer already uses (ui/index.html's html[data-theme="jarvis"] block; see
; the note beside MUI_BGCOLOR near the top of this file). NSIS wants RRGGBB
; with no hash, same convention as MUI_BGCOLOR/MUI_TEXTCOLOR above.
!define NAMEOS_DIM   "A9B0B5"             ; --dim.  Waiting: recedes, not yet under way.
!define NAMEOS_INK   "${MUI_TEXTCOLOR}"   ; --text. Active: the one row reading right now.
; Done uses NAMEOS_ACCENT directly (defined above, beside MUI_BGCOLOR) --
; nothing new needed, it is the same accent every other themed page uses.

; The five capability lines. Every one of them is traceable to something that
; actually ships rather than invented for the page -- Q1 and Q5 of
; ONBOARDING-SPEC.md, and the seed files seed_workdir() writes into a fresh
; vault on first open (src-tauri/src/main.rs). Never a specialist named here:
; ONBOARDING-SPEC.md's own build note says "don't over-promise the crew,"
; and this installer has no way to know which ones a given build exposes.
; ONLY FOUR OF THE FIVE ARE EVER SHOWN, as of 2026-08-29 -- see the note beside
; the STEP 4 DONE checkpoint in Section "helloim.ai" for why CAPTION_5 stays
; defined but unused. Left as five lines here regardless: the copy is real and
; correct, and which four actually get seen depends on how fast the machine
; running Setup is.
; NO APOSTROPHES BELOW, AND THAT IS NOT A STYLE CHOICE. Every System::Call
; further down is a single-quoted NSIS string; a literal ' inside a !define
; substituted into one closes it early and the rest of the instruction gets
; mangled into something the parser accepts without a warning -- CreateWindowEx
; then calls through as garbage. Reproduced: "that's"/"you'd"/"There's" in an
; earlier draft of these two lines crashed the compiled installer under wine
; with EIP 00000000 (a jump through a null pointer) on the real Directory
; page, and reproduced again in an isolated five-control sandbox script built
; specifically to rule out everything else about the real Section. Write
; "is"/"would" instead. Costs nothing a reader notices.
;
; THE DASH IS A REAL EM DASH, NOT `--`, and this one did not need a probe to
; know it is safe: MUI_WELCOMEPAGE_TEXT above already carries a literal em
; dash on the SAME body font ($NameOS_StepFont, the caption's font, is the
; same control-borrowed font as the Welcome page text), and it has been
; rendering correctly in every screenshot since before this file's own step
; list existed. The checkmark glyph tofu-boxed because it needed a symbol
; font the caption never asks for; punctuation is not in that category.
!define NAMEOS_CAPTION_1 "Give it a name — that is the first thing it asks, and it is yours."
!define NAMEOS_CAPTION_2 "Ask it the way you would ask a person. Nothing to memorize."
!define NAMEOS_CAPTION_3 "Your notes link to each other, so it learns how your work fits together."
!define NAMEOS_CAPTION_4 "Natural voices are built in. Nothing extra to download, nothing extra to set up."
!define NAMEOS_CAPTION_5 "You decide how much it does on its own before it checks in with you."

; THE PAGE BODY WAS STOCK LIGHT GREY -- corrected 2026-08-29, same Jarvis
; screenshot review that caught the ASCII markers. MUI_BGCOLOR (top of this
; file) only reaches the Welcome and Finish pages -- both are the bitmap
; pages MUI2 hands to the wizard whole, background included. InstFiles is
; not: it is the fixed dialog template inside modern.exe, and nothing in MUI2
; exposes a define for ITS background the way MUI_BGCOLOR does for the other
; two. Proven by trying rather than assumed: a subclassed WM_CTLCOLORDLG would
; do it properly, and subclassing means handing a native window procedure a
; function pointer obtained from GetFunctionAddress -- the exact unverified
; native-callback ABI already declined for the timer, for the same reason.
;
; THE FIX THAT SHIPS IS THE SAME TRICK BEHIND EVERY COLOURED PANEL IN CLASSIC
; WIN32, NOT A DIALOG-LEVEL OVERRIDE: an ordinary STATIC control, no text,
; sized to the whole area below the progress bar, coloured black through the
; SAME SetCtlColors this whole file already uses safely everywhere else. A
; STATIC's own DefWindowProc paints its WM_CTLCOLORSTATIC brush across its
; entire rect before anything else, which is the whole mechanism -- no
; subclassing, no callback, nothing this file has not already proven safe.
; IT MUST BE PUSHED TO THE BOTTOM OF Z-ORDER, EXPLICITLY. A window created
; later is a newer sibling, and newer siblings paint on top by default -- left
; alone, this panel would be created after the progress bar and status text
; MUI2 built long before this function ever runs, and being on top would hide
; them completely. SetWindowPos(..., HWND_BOTTOM, ...) right after creating it
; fixes that with a second, ordinary, non-callback Win32 call.
Var NameOS_Panel
Var NameOS_Step1
Var NameOS_Step2
Var NameOS_Step3
Var NameOS_Step4
Var NameOS_Caption
Var NameOS_StepFont    ; borrowed body font, for the caption line
Var NameOS_GlyphFont    ; Segoe UI Symbol (or whatever fc-match gives it), for the four step rows
Var NameOS_CaptionTick     ; GetTickCount() when the caption text last actually changed -- set on
                           ; both of this page's two caption swaps; nothing currently reads it back,
                           ; kept for the day there is a real intermediate checkpoint to gate again

Function NameOS_InstFilesShow
  ; THE PROGRESS BAR WAS STOCK GREEN -- Beck's real-hardware finding,
  ; 2026-08-29: RGB(15,123,15) on a light grey trough, the loudest colour on
  ; the page once everything around it went dark with cyan accents.
  ; PBM_SETBARCOLOR/PBM_SETBKCOLOR are IGNORED by a THEMED (visual-styles)
  ; progress bar on modern Windows -- they only take effect once the control
  ; is un-themed. SetWindowTheme with two NULL strings does that, targeted at
  ; JUST this one control's own hwnd -- NOT MUI_FORCECLASSICCONTROLS, which
  ; was already tried and rejected for the Finish checkbox because it
  ; un-themes the WHOLE dialog, not one control (see that page's own notes).
  ; A plain, synchronous, non-callback Win32 call -- same category as every
  ; other System::Call already proven safe in this file, nothing like the
  ; native-callback risk that ruled out a real timer.
  ; COLORREF is 0x00BBGGRR, not RRGGBB: accent 8FE6FF becomes 0x00FFE68F.
  System::Call 'UXTHEME::SetWindowTheme(p $mui.InstFilesPage.ProgressBar, w0, w0) i'
  SendMessage $mui.InstFilesPage.ProgressBar ${PBM_SETBARCOLOR} 0 "0x00FFE68F"
  ; TROUGH WAS 0x00000000 -- BLACK ON THE BLACK PANEL, SEE NAMEOS_TROUGH's OWN
  ; NOTE NEAR THE TOP OF THIS FILE. Same COLORREF conversion as the accent
  ; line above: NAMEOS_TROUGH 33383D becomes 0x003D3833. A value change only,
  ; same PBM_SETBKCOLOR call that was already proven working -- the fill was
  ; never the problem, the empty state was.
  SendMessage $mui.InstFilesPage.ProgressBar ${PBM_SETBKCOLOR} 0 "0x003D3833"

  ; THE BAR WAS ONLY ON SCREEN 11% OF THE TIME -- Beck's real-hardware
  ; finding, 2026-08-29, and this is a repaint bug, not a colour one: sampling
  ; the bar's exact rect every 250ms across a full 9.45s install, it was
  ; present in 2 of 18 samples, both times immediately after PBM_SETPOS moved
  ; it -- PBM_GETPOS itself advanced correctly throughout, so progress
  ; reporting was never the problem. Her Z-order dump explains it: the black
  ; panel created below (NameOS_Panel) sits BELOW the bar in Z-order with its
  ; own rect fully containing the bar's, and NEITHER control carried
  ; WS_CLIPSIBLINGS. A STATIC repaints on any WM_ERASEBKGND, not only when
  ; this file explicitly touches it, so every panel repaint painted straight
  ; over its own higher-Z sibling -- the bar only reappeared when a position
  ; change forced IT to redraw on top again.
  ;
  ; THE FIX IS ON THE PANEL, NOT THE BAR -- see its own CreateWindowEx call
  ; below, now built with WS_CLIPSIBLINGS in its style. That flag excludes any
  ; overlapping sibling from a window's OWN paint region; setting it on the
  ; panel stops the panel drawing over the bar, which is the only direction
  ; this ever broke in -- the bar's rect sits entirely inside the panel's, so
  ; the bar redrawing never had anything of the panel's to paint over. The bar
  ; itself is a native MUI2 control this file did not create, and there is
  ; nothing measured here that a matching flag on it would fix.

  ; Borrow the font MUI2's own status line (control 1006) already uses for the
  ; caption, so the capability lines do not stand out as a different typeface
  ; glued onto the page. $mui.InstFilesPage.Text is a Var MUI2 itself
  ; populates via GetDlgItem just above where this function is inserted
  ; (InstallFiles.nsh, MUI_FUNCTION_INSTFILESPAGE) -- already valid here.
  System::Call 'USER32::SendMessage(p $mui.InstFilesPage.Text, i ${WM_GETFONT}, i0, i0) p.r0'
  StrCpy $NameOS_StepFont $0

  ; A SEPARATE FONT FOR THE FOUR STEP ROWS -- see the marker note above for
  ; why: this is what makes the hollow/filled circle glyphs paint instead of
  ; tofu-boxing, and it renders their plain-Latin labels beside them without
  ; trouble too, so one font covers the whole row. LOGFONT fields in order:
  ; lfHeight lfWidth lfEscapement lfOrientation lfWeight lfItalic lfUnderline
  ; lfStrikeOut lfCharSet lfOutPrecision lfClipPrecision lfQuality
  ; lfPitchAndFamily lfFaceName[32 wide chars]. Height/weight copied from a
  ; typical Segoe UI status-line metric (-16, FW_NORMAL 400) rather than read
  ; off $NameOS_StepFont, so this does not depend on that call having already
  ; run -- cheap and it cannot end up depending on function-call order later.
  System::Call '*(i-16,i0,i0,i0,i400,i0,i0,i0,i0,i0,i0,i0,i0,&t64 "Segoe UI Symbol") p.r0'
  System::Call 'GDI32::CreateFontIndirect(p r0) p.r1'
  StrCpy $NameOS_GlyphFont $1
  System::Free $0

  ; THE PANEL WAS AN ISLAND -- corrected 2026-08-29, third pass, after Jarvis
  ; looked at final-install-B.png: a black rectangle floating in the middle of
  ; a still-light page, because it only covered the area BELOW the progress
  ; bar. It now starts at y=0 -- the very top of $mui.InstFilesPage's own
  ; client rect -- rather than y=40, so it also sits behind the progress bar
  ; row and the "Extract: X... N%" status line, closing the light band that
  ; used to sit between the header and the black area. $mui.InstFilesPage.Text
  ; (the status line) gets its own colour set to match, immediately below --
  ; left unset it would be black-on-black once this panel is behind it, which
  ; is a worse failure than the light band it replaces: invisible instead of
  ; ugly. The progress bar control itself (1004) is left alone deliberately --
  ; it is opaque and paints its own native chrome regardless of what is behind
  ; it, and a light progress bar on a dark page is an ordinary, expected look
  ; the whole rest of this file already accepts (the button row at the very
  ; bottom of the page stays the standard system colour for the same reason:
  ; it is a native control, not empty page background).
  ;
  ; STILL CREATED FIRST, THEN EXPLICITLY PUSHED TO HWND_BOTTOM (1) -- a window
  ; created later is a newer sibling, and newer siblings paint on top by
  ; default; left alone this panel would hide the progress bar and status text
  ; MUI2 built long before this function ever runs. SWP_NOMOVE|SWP_NOSIZE|
  ; SWP_NOACTIVATE = 0x0013.
  ;
  ; MEASURED, NOT GUESSED -- Beck's real-hardware finding, 2026-08-29: the old
  ; hardcoded 520x320 overhung the dialog by 43px on the right (panel right
  ; edge 3294 against the window's own right edge of 3251) and 29px on the
  ; bottom (951 against 922). The "sized generously" reasoning that used to sit
  ; here was true as far as it went -- a child cannot PAINT outside its
  ; parent's client area, Win32 clips that automatically -- but it said nothing
  ; about the window's own declared RECT outliving that clip, which is exactly
  ; what Beck measured. GetClientRect on $mui.InstFilesPage itself, right here,
  ; is the source of truth for whatever machine Setup is actually running on,
  ; rather than a number picked once against this box's own wine rig. Same
  ; non-callback, synchronous Win32 call as everything else already proven
  ; safe in this file, against the SAME handle this function already uses
  ; successfully as the parent for every CreateWindowEx call below -- unlike
  ; the FinishPage GetWindowRect call ruled out elsewhere in this file, there
  ; is no history of this handle answering unreliably.
  ;
  ; FALLS BACK TO THE OLD 520x320 IF THE READ FAILS OR RETURNS NOTHING
  ; USABLE, so a GetClientRect that ever comes back empty degrades to exactly
  ; today's behaviour rather than a zero-sized or missing panel.
  System::Call '*(i,i,i,i) p.r0'
  System::Call 'USER32::GetClientRect(p $mui.InstFilesPage, p $0) i.r1'
  System::Call '*$0(i,i,i.r2,i.r3)'
  System::Free $0
  StrCmp $1 "0" nameos_panel_fallback
  IntCmp $2 1 nameos_panel_have_size nameos_panel_fallback nameos_panel_have_size
  nameos_panel_fallback:
    StrCpy $2 520
    StrCpy $3 320
  nameos_panel_have_size:
  ; WS_CHILD|WS_VISIBLE|WS_CLIPSIBLINGS = 0x54000000 -- see the note beside the
  ; progress-bar colour calls above the top of this function for why
  ; WS_CLIPSIBLINGS is the actual fix and what it was costing without it.
  System::Call 'USER32::CreateWindowEx(i0, t"STATIC", t"", \
    i0x54000000, i0, i0, i $2, i $3, p $mui.InstFilesPage, i0, i0, i0) p.r1'
  StrCpy $NameOS_Panel $1
  System::Call 'USER32::SetWindowPos(p $NameOS_Panel, p 1, i0,i0,i0,i0, i0x0013)'
  ; QUIETED, THEN HIDDEN OUTRIGHT -- 2026-08-29, second pass. Dimming it (DIM
  ; instead of INK, the fix that shipped first) made it worse, not better:
  ; against the old stock light page it receded; against this panel's true
  ; black a light-grey line is MORE legible than it was before, the opposite
  ; of the point of this whole redesign. The step list plus the progress bar
  ; already carries everything a person watching this page needs -- a raw
  ; "Extract: kokoro.onnx... 57%" line under it is exactly the file-log
  ; texture this page exists to remove.
  ;
  ; So it is hidden outright rather than recoloured again. This is the same
  ; call, on the same category of control, already proven safe in this file:
  ; NameOS_FinishPageShow hides $mui.FinishPage.Run this identical way
  ; (`USER32::ShowWindow(..., i0)`, SW_HIDE) and Finish.nsh's own LEAVE
  ; function goes on reading that control's state afterward without incident.
  ; $mui.InstFilesPage.Text is populated by MUI2's own SHOW handler via
  ; GetDlgItem BEFORE this function runs (InstallFiles.nsh, confirmed by
  ; reading the copy of that file actually installed on this box) -- so the
  ; handle is valid here, and hiding it does not stop NSIS's own core from
  ; writing status text into it on every file operation, it only stops that
  ; text from painting. Nothing else in InstallFiles.nsh reads this control's
  ; visibility or re-shows it, so one hide here holds for the rest of the page.
  ; SetCtlColors is left in place rather than deleted -- if a future build
  ; ever needs the raw line back, uncommenting the ShowWindow call below is
  ; the whole change, and the colour is already right for that case too.
  SetCtlColors $mui.InstFilesPage.Text "${NAMEOS_DIM}" "${MUI_BGCOLOR}"
  System::Call 'USER32::ShowWindow(p $mui.InstFilesPage.Text, i0)'   ; SW_HIDE

  ; THE HEADER STRIP WAS TRIED AND TAKEN BACK OUT -- Jarvis asked for the same
  ; trick on the header, and to say plainly rather than claim it worked if it
  ; did not. It did not. A panel targeting $HWNDPARENT at (0,0,520,52), pushed
  ; to HWND_BOTTOM exactly like the body panel above, did not sit behind the
  ; header bitmap and its title/subtitle text -- it erased them. Built and run
  ; under wine: the header strip came back solid black, no circuit bitmap, no
  ; "Installing" title, no subtitle, nothing behind the panel at all, on the
  ; real installer with its real bitmap. Welcome and Finish do not have this
  ; problem because MUI2 hands the WHOLE page to one bitmap; the InstFiles
  ; header is composed of separate controls this file has no confirmed handle
  ; on, and $HWNDPARENT was a guess at their parent, not a measured fact --
  ; unlike $mui.InstFilesPage, which MUI2's own generated code hands this
  ; function directly. HWND_BOTTOM either did not reach whatever window those
  ; controls actually belong to, or they belong to a DIFFERENT window than
  ; $HWNDPARENT entirely, and either way the honest result is the header is
  ; gone, not dark. A body with a stray light header is a real page; a header
  ; with nothing on it is not, so this was taken back out rather than shipped.
  ; Finding the header controls' real owner (EnumChildWindows over $HWNDPARENT
  ; with GetClassName, rather than guessing) is the next real step here, and
  ; it was not spent on tonight.
  SetCtlColors $NameOS_Panel "" "${MUI_BGCOLOR}"

  ; WS_CHILD|WS_VISIBLE = 0x50000000. Parented to $mui.InstFilesPage, the same
  ; handle MUI2's own controls (progress bar, status text) are children of, so
  ; these move and hide with the page exactly like MUI2's own controls do.
  ;
  ; Step 1 is created ACTIVE, not waiting -- Section "helloim.ai" starts executing
  ; the moment this page is shown, there is no click that starts it, so a
  ; "waiting" first row would be describing something already under way.
  System::Call 'USER32::CreateWindowEx(i0, t"STATIC", t"${NAMEOS_STEP1_ACTIVE}", \
    i0x50000000, i20, i66, i440, i16, p $mui.InstFilesPage, i0, i0, i0) p.r1'
  StrCpy $NameOS_Step1 $1
  System::Call 'USER32::SendMessage(p $NameOS_Step1, i ${WM_SETFONT}, p $NameOS_GlyphFont, i1)'
  SetCtlColors $NameOS_Step1 "${NAMEOS_INK}" "${MUI_BGCOLOR}"

  System::Call 'USER32::CreateWindowEx(i0, t"STATIC", t"${NAMEOS_STEP2_WAIT}", \
    i0x50000000, i20, i84, i440, i16, p $mui.InstFilesPage, i0, i0, i0) p.r1'
  StrCpy $NameOS_Step2 $1
  System::Call 'USER32::SendMessage(p $NameOS_Step2, i ${WM_SETFONT}, p $NameOS_GlyphFont, i1)'
  SetCtlColors $NameOS_Step2 "${NAMEOS_DIM}" "${MUI_BGCOLOR}"

  System::Call 'USER32::CreateWindowEx(i0, t"STATIC", t"${NAMEOS_STEP3_WAIT}", \
    i0x50000000, i20, i102, i440, i16, p $mui.InstFilesPage, i0, i0, i0) p.r1'
  StrCpy $NameOS_Step3 $1
  System::Call 'USER32::SendMessage(p $NameOS_Step3, i ${WM_SETFONT}, p $NameOS_GlyphFont, i1)'
  SetCtlColors $NameOS_Step3 "${NAMEOS_DIM}" "${MUI_BGCOLOR}"

  System::Call 'USER32::CreateWindowEx(i0, t"STATIC", t"${NAMEOS_STEP4_WAIT}", \
    i0x50000000, i20, i120, i440, i16, p $mui.InstFilesPage, i0, i0, i0) p.r1'
  StrCpy $NameOS_Step4 $1
  System::Call 'USER32::SendMessage(p $NameOS_Step4, i ${WM_SETFONT}, p $NameOS_GlyphFont, i1)'
  SetCtlColors $NameOS_Step4 "${NAMEOS_DIM}" "${MUI_BGCOLOR}"

  ; The caption sits clear of the four rows with a real gap, not tight beneath
  ; them -- the Finish-page fix above already found out what happens to a
  ; sibling control placed too close to another one's own bounding rect.
  ; Two lines tall on purpose: the longer capability lines wrap once at this
  ; width, and clipping a line mid-word reads as a rendering fault.
  System::Call 'USER32::CreateWindowEx(i0, t"STATIC", t"${NAMEOS_CAPTION_1}", \
    i0x50000000, i20, i150, i440, i34, p $mui.InstFilesPage, i0, i0, i0) p.r1'
  StrCpy $NameOS_Caption $1
  System::Call 'USER32::SendMessage(p $NameOS_Caption, i ${WM_SETFONT}, p $NameOS_StepFont, i1)'
  SetCtlColors $NameOS_Caption "${NAMEOS_INK}" "${MUI_BGCOLOR}"
  ; Caption 1 shows unconditionally -- it is the first thing on screen, there
  ; is nothing before it to have dwelled. There is exactly one more caption
  ; swap in this whole page (Step1 Done / Step2 Active, below), and THAT one
  ; IS gated -- on progress remaining as well as dwell -- because unlike this
  ; one it has something real to be measured against. See the design note
  ; above (where NameOS_MaybeAdvanceCaption used to sit) and the checkpoint
  ; itself for why and how.
  System::Call 'KERNEL32::GetTickCount() i.r0'
  StrCpy $NameOS_CaptionTick $0
FunctionEnd

; TWO CAPTIONS AT MOST, GATED ON PROGRESS REMAINING -- corrected 2026-08-29,
; TWICE IN ONE DAY, and this is the version that stops guessing at wall-clock
; time altogether. The two attempts before this one both timed the swap and
; both failed the same way for a reason neither could see from this box:
;   1. Time the LAST swap only (protect the tail): Beck found the checkpoint
;      one swap earlier had the identical problem, for the identical reason.
;   2. Make the ONE remaining swap unconditional, reasoning that it fires
;      "early" (before the slow copy) on every machine: it fires at 1.54s on
;      this box's own wine rig -- and at roughly 7.8s on Beck's real hardware,
;      out of an 8.9-9.5s install. Wine's checkpoint order says nothing
;      reliable about wall-clock timing on the machine that actually ships,
;      and a fix built from wine timing alone reproduced the exact bug it was
;      meant to fix, just relocated from the last swap to the first.
;
; SO THIS VERSION DOES NOT TIME ANYTHING TO DECIDE WHETHER TO SWAP. It reads
; the progress bar's OWN position and range -- PBM_GETPOS and PBM_GETRANGE on
; $mui.InstFilesPage.ProgressBar, the exact control this file already colours
; a few lines up -- and asks what fraction of the whole install is left, which
; is the one number that means the same thing on every machine regardless of
; why any particular phase happens to be fast or slow there. See the
; checkpoint itself, below, for the exact calculation and its sources.
;
; THE RULE: if less than about half the installed bytes remain at the
; checkpoint, do not swap -- leave caption 1 up for the rest of the install
; rather than hand caption 2 a sliver of what's left. The 2.5-second dwell
; floor stays as a SECOND, independent gate on top of it (both must pass): the
; progress check says there is probably enough of the install left to be
; worth swapping into, the dwell floor says caption 1 has actually had a
; moment to be read first. Neither alone was enough on its own in the two
; attempts above.
;
; THE HONEST OUTCOME IS ONE CAPTION ON SOME MACHINES, AND THAT IS CORRECT, NOT
; A REGRESSION. A fast copy that finishes most of the install before this
; checkpoint even fires leaves caption 1 up the whole time -- a single line a
; person actually reads beats a second one truncated to a fraction of a
; second, which is the exact failure this whole redesign exists to stop.
; NAMEOS_CAPTION_3, 4 and 5 stay defined above, unused, real accurate copy,
; ready for a genuine mid-copy checkpoint (splitting the two tts File calls
; with one, say) the same way they already were before this pass.
;
; WINE'S OWN TIMING DOES NOT SETTLE THIS. Verified here: the progress read
; itself is correct (position and range come back live and change as the
; install proceeds, matching what Beck read off the same messages on real
; hardware), and the gate's arithmetic and its fail-closed branch were sampled
; through a full install the same way the bar was. What wine CANNOT prove is
; whether Beck's real machine lands above or below the half-remaining line at
; this checkpoint -- that depends on real disk and AV behaviour this box does
; not reproduce. Only her rig settles that, and this comment is not the place
; to guess at it.
;
; THE DWELL-GATE FUNCTION THAT USED TO SIT HERE (NameOS_MaybeAdvanceCaption)
; stays gone rather than being rebuilt as a function -- there is exactly one
; swap site again, same as the version before this one, so its dwell check is
; inlined at that one checkpoint instead of reintroducing a function with a
; single caller. makensis strips and warns on an unreferenced function, which
; is what took the earlier version of this function out in the first place;
; that reasoning has not changed.

; MUI_PAGE_CUSTOMFUNCTION_SHOW IS NOT FINISH-PAGE-SPECIFIC -- every one of the
; five MUI_PAGE_* macros above reads and then MUI_UNSETs the same generic
; define. Defining it up with the other MUI_FINISHPAGE_* settings near the top
; of this file, before MUI_PAGE_WELCOME, silently wires it onto the WELCOME
; page instead: Welcome consumes it first, and Finish gets nothing. The second
; build of this fix compiled clean and rendered a perfectly correct dark Finish
; page with the checkbox label still invisible -- no error, because a hook that
; attaches to the wrong page is not a compile fault, it just quietly does
; nothing where you're looking. Caught by finding no second Static in the
; Finish page's own control dump, not by any warning. So this define sits
; here, immediately before the ONE page macro it is meant for, and nowhere else
; touches it.
!define MUI_PAGE_CUSTOMFUNCTION_SHOW NameOS_FinishPageShow
!insertmacro MUI_PAGE_FINISH

; THE POSITION IS COPIED, NOT GUESSED. MUI2 unsets MUI_FINISHPAGE_RUN_TOP the
; moment the page macro above finishes expanding, so it cannot be read from
; here -- this recomputes it by the identical formula Finish.nsh uses:
; TITLE_HEIGHT 28 (no MUI_FINISHPAGE_TITLE_3LINES here) -> TEXT_TOP 17+28=45 ->
; TEXT_HEIGHT_BUTTONS 40 (no MUI_FINISHPAGE_TEXT_LARGE here) ->
; TEXT_BOTTOM_BUTTONS 45+40=85 -> RUN_TOP 85+5=90. 120u and 195u are the
; literal numbers Finish.nsh passes to ${NSD_CreateCheckbox} for this control.
; If MUI_FINISHPAGE_SHOWREADME, a 3-line title, large finish text, or reboot
; support are ever added to this page, this needs re-deriving the same way --
; it will not update itself.
;
; THE LABEL SAT BELOW THE CHECKBOX FOR A REAL REASON, AND REAL WINDOWS THEN
; FOUND A DIFFERENT BUG IN THAT FIX -- kept the history rather than deleting
; it, because the reasoning below is still exactly why "beside it" failed the
; FIRST time this was tried. It was tried beside the checkbox first, offset 12
; dialog units clear of the glyph, and it compiled, created the control, at
; the position the tree dump confirmed, with SetCtlColors returning no error
; -- and never once rendered, not even swapped to solid red-on-green to rule
; out a colour problem, not after forcing the window to repaint with a
; minimize/restore cycle. The reason: 120u to 315u was the checkbox's WHOLE
; window rect, not just its visible glyph -- the other ~183u of that width was
; where its own (invisible) text would have drawn. A label placed anywhere in
; that span was a SIBLING window living inside the checkbox's own bounding
; rectangle, and whichever of the two was higher in z-order won every
; repaint. Moving the label below it, clear of that rect entirely, was the
; fix that shipped.
;
; REAL WINDOWS THEN FOUND WHAT "BELOW IT" COST -- Beck, release verification,
; 2026-08-29, on real hardware, not Wine: blanking the checkbox's own text
; (below) left the control at its full 195u width, and a control's focus
; rectangle wraps its whole client rect whether it has text or not. So the
; page showed a ticked box, then a page-wide dotted rectangle that reads as
; an empty field waiting for input, then "Launch helloim.ai now" orphaned on the
; row underneath. Two genuine bugs, from two genuine fixes, each solving the
; one before it.
;
; THE FIX WAS TRIED AS A RESIZE, AND THAT ATTEMPT IS ABANDONED, NOT SHIPPED --
; corrected 2026-08-29, same review round. GetWindowRect on $mui.FinishPage.Run
; returned an all-zero rect -- proven wrong twice under wine, once on a fresh
; install and once on a repair, not a one-off -- while the IDENTICAL
; struct-marshaling pattern worked correctly for the LOGFONT call on the
; InstFiles page a few hundred lines up. Never fully root-caused: the
; timing difference between the two hook points (Finish's own SHOW fires
; before nsDialogs::Show ever runs, per Finish.nsh's own code -- InstFiles'
; does not have that ordering at all, it is not an nsDialogs page) is the
; leading theory, not a proof. Chasing an intermittent GetWindowRect failure
; further was the wrong trade for a cosmetic fix -- "if it still fights, say
; so and take the native text back instead" was the standing instruction, and
; this is that, in a form that keeps the duplicate-text fix rather than
; discarding it too.
;
; THE FIX THAT SHIPS USES ONLY THE SAME 'u'-BASED nsDialogs MACROS THIS
; FUNCTION ALREADY PROVED RELIABLE (${NSD_CreateCheckbox}, ${NSD_CreateLabel})
; rather than raw Win32 geometry calls. $mui.FinishPage.Run is NEVER resized
; or moved -- it is HIDDEN, and keeps tracking its own checked state exactly
; as MUI2 built it, because Finish.nsh's own LEAVE function reads that
; control's check state via BM_GETCHECK at the very end of the page, and that
; has to keep working undisturbed regardless of anything done here. A NEW,
; small, REAL checkbox is created at the SAME 120u/90u position with a 14u
; width instead of 195u -- a checkbox glyph does not need 195u to draw
; itself, and at 14u there is no shared bounding rectangle left for a label
; beside it to fight over, which is the exact condition the earlier "beside
; it" attempt (see the history above) was reaching for and did not have.
; Clicking either the new checkbox or the label relays onto the original
; (hidden) one, so the one thing Finish.nsh actually reads never sees
; anything different from before.
Var FinishRunLabel
Var FinishRunCheckbox

Function NameOS_FinishPageShow
  System::Call 'USER32::ShowWindow(p $mui.FinishPage.Run, i0)'   ; SW_HIDE

  ${NSD_CreateCheckbox} 120u 90u 14u 10u ""
  Pop $FinishRunCheckbox
  SetCtlColors $FinishRunCheckbox "${MUI_TEXTCOLOR}" "${MUI_BGCOLOR}"
  ; Starts matching whatever MUI2 already set the original to (checked by
  ; default, per Finish.nsh, unless MUI_FINISHPAGE_RUN_NOTCHECKED is defined
  ; -- it is not, here) rather than assuming a state.
  ${NSD_GetState} $mui.FinishPage.Run $0
  ${NSD_SetState} $FinishRunCheckbox $0
  ${NSD_OnClick} $FinishRunCheckbox NameOS_FinishRunRelayClick

  ${NSD_CreateLabel} 137u 90u 178u 10u "${NAMEOS_FINISHRUN_LABEL_TEXT}"
  Pop $FinishRunLabel
  SetCtlColors $FinishRunLabel "${MUI_TEXTCOLOR}" "${MUI_BGCOLOR}"
  ${NSD_OnClick} $FinishRunLabel NameOS_FinishRunLabelClick
FunctionEnd

; The visible checkbox already toggled ITSELF -- a real checkbox, a real
; click -- by the time this fires. All that is left is relaying its new state
; onto the hidden original, which is the one control Finish.nsh actually
; reads when the page is left.
Function NameOS_FinishRunRelayClick
  Pop $0 ; nsDialogs passes the clicked control's own hwnd; not needed here
  ${NSD_GetState} $FinishRunCheckbox $0
  ${NSD_SetState} $mui.FinishPage.Run $0
FunctionEnd

; Clicking the WORDS should do what clicking a checkbox's own label always
; does -- toggle the box. Nothing toggles itself for a label click, unlike the
; checkbox's own relay above, so this flips the visible checkbox explicitly
; and then relays exactly the same way a real click on it would have.
Function NameOS_FinishRunLabelClick
  Pop $0 ; nsDialogs passes the clicked control's own hwnd; not needed here
  ${NSD_GetState} $FinishRunCheckbox $0
  StrCmp $0 ${BST_CHECKED} nameos_run_uncheck nameos_run_check
  nameos_run_check:
    ${NSD_Check} $FinishRunCheckbox
    Goto nameos_run_toggled
  nameos_run_uncheck:
    ${NSD_Uncheck} $FinishRunCheckbox
  nameos_run_toggled:
  ${NSD_GetState} $FinishRunCheckbox $0
  ${NSD_SetState} $mui.FinishPage.Run $0
FunctionEnd

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; If helloim.ai is already installed, running Setup again should not silently
; reinstall — it should ask. We detect the prior install by its Add/Remove
; Programs uninstall entry and offer Repair (reinstall this version over the
; top) or Uninstall (run the existing uninstaller), or do nothing.
; Set when the in-app updater is the one running us. The updater always appends
; /UPDATE to the installer's command line, so this is its signature and not a
; guess about who started us.
Var IsUpdate

Function .onInit
  ; --- IS THIS AN UPDATE? ---
  ; THIS BLOCK IS WHY A SILENT UPDATE DOES NOT HANG. Everything below it can
  ; put a dialog on screen, and during an update there is no window for one to
  ; appear over -- the app has just exited. A MessageBox in a silent run waits
  ; for a click that will never come, on a box the person thinks is idle.
  StrCpy $IsUpdate 0
  ${GetParameters} $R9
  ClearErrors
  ${GetOptions} $R9 "/UPDATE" $R8
  IfErrors +2 0
    StrCpy $IsUpdate 1

  ; HKCU now — same hive this installer writes to. It also reads HKLM below,
  ; because anyone upgrading from a build before 2026-08-27 has an ELEVATED
  ; install in Program Files that this one cannot overwrite and must not
  ; silently duplicate.
  ReadRegStr $R0 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}" "UninstallString"
  StrCmp $R0 "" 0 have_prior
    ReadRegStr $R0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}" "UninstallString"
    StrCmp $R0 "" have_prior 0
      ; THE OLD MACHINE-WIDE COPY. Leaving it is the "I uninstalled it and it
      ; still runs" fault this file already has a scar about, one directory
      ; up: two helloim.ai installs, and the one in Program Files never updates
      ; again because nothing unelevated can write to it.
      ;
      ; NEVER SHOWN UNATTENDED -- Beck, build b15. She could not exercise this
      ; branch at all (her test account is not a local admin and HKLM is not
      ; writable there), which made it the one path in this file nobody had
      ; actually run before shipping -- and it is not a rare combination to
      ; miss: the in-app updater launches this installer with /UPDATE from
      ; inside the very process that would trip it, for anyone who installed
      ; the old elevated build and lets helloim.ai update itself. A MessageBox
      ; here waits for a click that an /UPDATE or /S run has nobody to give.
      ;
      ; SAME DEFAULT THE REPAIR/UNINSTALL PROMPT FURTHER DOWN ALREADY USES,
      ; FOR THE SAME REASON (see IfSilent fresh, below): do nothing
      ; destructive unattended. Silently running the old uninstaller here
      ; would trade one hang for another -- that build predates the per-user
      ; pivot, so ITS uninstaller is itself elevated, and `ExecWait '"$R0"
      ; /S'` would raise a UAC prompt with nobody unattended to answer it.
      ; So an unattended run leaves the legacy copy exactly where it is and
      ; installs the new per-user copy alongside it -- $R0 is cleared first,
      ; so the "install where it is already installed" logic just below does
      ; not redirect this install into the old copy's Program Files folder.
      ; The two-installs state this whole block exists to prevent is only
      ; ever resolved by a person answering the dialog; an unattended run
      ; defers that to the next time Setup is opened by hand, the same way
      ; the later prompt already defers its own decision.
      StrCmp $IsUpdate 1 unattended_skip_legacy
      IfSilent unattended_skip_legacy
      Goto legacy_prompt_ok
      unattended_skip_legacy:
        StrCpy $R0 ""
        Goto have_prior
      legacy_prompt_ok:
      MessageBox MB_OKCANCEL|MB_ICONINFORMATION \
"${APP} is currently installed for all users, which is why Windows keeps \
asking for permission.$\n$\n\
This version installs just for you and never asks again. The old copy needs \
removing first — that step still needs one permission prompt." \
        IDOK 0 IDCANCEL abort_old
      ExecWait '"$R0" /S'
      StrCpy $R0 ""
      Goto have_prior
    abort_old:
      Quit
  have_prior:

  ; INSTALL WHERE IT IS ALREADY INSTALLED, derived from the uninstaller's path
  ; in HKLM rather than from InstallDirRegKey. That key is under HKCU, and this
  ; installer always runs elevated -- so HKCU is the ADMIN's hive, not
  ; necessarily the hive of the person who chose the folder. Someone who
  ; installed to D:\Apps\helloim.ai would otherwise get an update quietly laid down
  ; in Program Files, leaving two helloim.ai installs and one of them stale.
  ; NEVER A RELATIVE JUMP OVER A MACRO. This was `StrCmp $R0 "" +3 0`, meaning
  ; "not installed, so skip the two lines below and keep the InstallDir default".
  ; ${GetParent} is not one instruction -- it expands to Push / Call / Pop, and
  ; the artificial-function form adds a Goto and the whole inlined body on first
  ; use. So +3 landed INSIDE the expansion, popped a value nobody pushed, and ran
  ; StrCpy $INSTDIR $R1 with the garbage. $INSTDIR came out EMPTY.
  ;
  ; THE SCAR, 2026-08-27. It only bites on a machine where helloim.ai is NOT already
  ; installed -- with it installed, $R0 is non-empty and this branch is never
  ; taken. So it survived every test on a box that had it, and Mark hit it the
  ; first time he ran Setup after uninstalling: Destination Folder blank, Install
  ; greyed out, no way forward. A label cannot be miscounted by a macro.
  StrCmp $R0 "" no_prior_install 0
    ${GetParent} "$R0" $R1
    StrCpy $INSTDIR $R1
  no_prior_install:

  ; SHOW THE INSTALLED VERSION ON THE PAGE BELOW, NOT JUST "already
  ; installed" -- ported from helloim.ai's build/installer.nsh (customInit's
  ; $R6), which reads DisplayVersion under the same key
  ; registryAddInstallInfo already wrote and shows it so the choice in front
  ; of the person is concrete: "1.2.0 is here, repair to 1.3.0" reads as a
  ; real decision, "helloim.ai is already installed" does not. Read from HKCU
  ; specifically, not the generic two-hive fallback .onInit uses higher up:
  ; by this point $R0 can only be non-empty because of the HKCU read a few
  ; lines above -- the one HKLM branch that could have set it already cleared
  ; $R0 back to "" after removing that old copy (see "StrCpy $R0 """ above),
  ; so whatever install this describes is always the per-user one, and $R0
  ; is still that install's own UninstallString -- the exact value
  ; NameOS_AlreadyInstalledUninstallClick, below, later hands to ExecWait.
  ;
  ; Computed here, unconditionally whenever $R0 is non-empty, rather than
  ; only for the cases that will actually show a prompt: harmless either way
  ; (a plain registry read, no UI), and it means the update/silent/skip
  ; decision itself lives in exactly one place --
  ; NameOS_AlreadyInstalledPageCreate's own Abort-to-skip check, further
  ; down -- instead of being duplicated and risking drifting apart from it.
  StrCmp $R0 "" no_already_installed_page
    ReadRegStr $R4 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}" "DisplayVersion"
    StrCmp $R4 "" 0 +2
      StrCpy $R4 "an earlier version"
  no_already_installed_page:
FunctionEnd

; THE ALREADY-INSTALLED PAGE ITSELF. See the long comment above `Page custom
; NameOS_AlreadyInstalledPageCreate`, near MUI_PAGE_WELCOME, for why this is
; a real page and not a MessageBox, and what changed 2026-09-02.
Var NameOSAlreadyDialog

Function NameOS_AlreadyInstalledPageCreate
  ; Skip this page outright -- no dialog, not even a flicker -- unless
  ; .onInit above found a genuine per-user install AND this run is neither
  ; the in-app updater (no window for anyone to answer a prompt on) nor
  ; silent. Same three conditions the retired MessageBox used to gate itself
  ; on, now the only place they are checked.
  StrCmp $IsUpdate 1 nameos_alreadyinst_skip
  IfSilent nameos_alreadyinst_skip
  StrCmp $R0 "" nameos_alreadyinst_skip
  Goto nameos_alreadyinst_build
  nameos_alreadyinst_skip:
    Abort ; inside a `Page custom` create function, Abort skips the page
  nameos_alreadyinst_build:

  nsDialogs::Create 1018
  Pop $NameOSAlreadyDialog
  StrCmp $NameOSAlreadyDialog error nameos_alreadyinst_skip
  SetCtlColors $NameOSAlreadyDialog "${MUI_TEXTCOLOR}" "${MUI_BGCOLOR}"

  ${NSD_CreateLabel} 0 0 100% 24u \
    "${APP} $R4 is already installed on this PC."
  Pop $0
  SetCtlColors $0 "${MUI_TEXTCOLOR}" "${MUI_BGCOLOR}"

  ${NSD_CreateLabel} 0 26u 100% 40u \
    "Click Next to repair it and update to ${VERSION}, over the existing \
install.$\r$\n$\r$\nOr, to remove ${APP} from this PC completely, use \
the button below."
  Pop $0
  SetCtlColors $0 "${NAMEOS_DIM}" "${MUI_BGCOLOR}"

  ; SEPARATE, BELOW, AND NOT THE DEFAULT CONTROL -- nsDialogs gives initial
  ; focus to the first control created on the page, which is Next's own
  ; wizard-chrome button, not this one; Enter at rest repairs, it does not
  ; uninstall. Its caption states the action outright, so there is no body
  ; text to skim past and no generic word standing in for what it does.
  ${NSD_CreateButton} 0u 80u 110u 14u "Uninstall ${APP}"
  Pop $0
  ${NSD_OnClick} $0 NameOS_AlreadyInstalledUninstallClick

  nsDialogs::Show
FunctionEnd

; THE SECOND, EXPLICIT CONFIRMATION. Everything that can actually touch disk
; from this page runs only after this box, and only on IDYES. Unlike the
; retired prompt, this box's own sentence names the action the button
; performs -- there is no separate headline promising something else for a
; button press to be misread against, and MB_YESNO here is a direct answer
; to the one question just asked, not a stand-in for a third, unstated
; outcome. MB_DEFBUTTON2 puts the dialog's own default focus on No, so
; landing here and pressing Enter out of habit does the safe thing.
Function NameOS_AlreadyInstalledUninstallClick
  Pop $0 ; nsDialogs passes the clicked control's own hwnd; not needed here

  MessageBox MB_YESNO|MB_ICONEXCLAMATION|MB_DEFBUTTON2 \
"This uninstalls ${APP} and removes everything it stored on this PC.$\n$\n\
This cannot be undone.$\n$\n\
Uninstall ${APP} now?" \
    IDYES nameos_alreadyinst_run_uninstall
  Return

  nameos_alreadyinst_run_uninstall:
  ; $R0 is the per-user UninstallString .onInit read from the registry --
  ; this page (and so this button) only exists when it is non-empty, see the
  ; skip check above, so this should never see it blank. Fail loud rather
  ; than clicking through to nothing if it somehow is.
  StrCmp $R0 "" nameos_alreadyinst_no_uninstaller
    ExecWait '"$R0" /S'
    Quit
  nameos_alreadyinst_no_uninstaller:
    MessageBox MB_OK|MB_ICONSTOP \
      "Could not find the ${APP} uninstaller. Use Windows Settings > \
Apps instead."
FunctionEnd

Section "${APP}" SecMain
  ; **DIAGNOSTIC INSTRUMENTATION -- TEMPORARY, added 2026-09-04 to chase the
  ; fresh-install exit-2 ship-blocker.** ONE handle, held open for the whole
  ; section, closed once right before the section ends (or right before the
  ; Abort) -- deliberately not many short open/close cycles, which produced
  ; a truncated, out-of-order log the first time this was tried. Purely
  ; additive -- no control flow below is changed by this pass. Remove once
  ; the real cause is confirmed and fixed for real.
  Delete "$TEMP\helloim-install-trace.log"
  FileOpen $9 "$TEMP\helloim-install-trace.log" w
  FileWrite $9 "section start$\r$\n"
  FileWrite $9 "IsUpdate=$IsUpdate$\r$\n"
  FileWrite $9 "INSTDIR=$INSTDIR$\r$\n"

  ; CLOSE THE RUNNING APP BEFORE OVERWRITING IT, and only during an update --
  ; the app is what launched us, and Windows will not let a running .exe be
  ; replaced. Without this the File instruction below fails, the installer
  ; reports success anyway in silent mode, and the person ends up on the old
  ; version wondering why the update did nothing.
  ;
  ; It waits and retries rather than killing once and hoping: the updater exits
  ; the app itself, so most of the time the first check finds nothing to do, and
  ; the loop is there for the case where shutdown takes a moment.
  StrCmp $IsUpdate 0 skip_kill
    DetailPrint "Closing ${APP}…"
    StrCpy $R5 0
    kill_loop:
      nsExec::ExecToStack 'cmd /c tasklist /fi "IMAGENAME eq helloim.ai.exe" /nh | find /i "helloim.ai.exe"'
      Pop $R6
      Pop $R7
      StrCmp $R6 "0" 0 skip_kill        ; find returned 1 -- nothing running
      nsExec::ExecToLog 'taskkill /F /IM helloim.ai.exe /T'
      Pop $R6
      Sleep 700
      IntOp $R5 $R5 + 1
      IntCmp $R5 8 skip_kill kill_loop skip_kill   ; equal / less / greater
  skip_kill:

  SetOutPath "$INSTDIR"

  ; THE RACE THE KILL LOOP ABOVE CANNOT FULLY CLOSE -- Beck's re-verification,
  ; 2026-08-29, THE PUBLICATION BLOCKER. Two runs of the identical /UPDATE
  ; against a running 0.1.0: one exited 0, wrote DisplayVersion 0.2.0 below,
  ; and left helloim.ai.exe itself untouched at 0.1.0 -- no error anywhere, no
  ; pending-rename to repair it at the next reboot, the machine offered the
  ; same update forever.
  ;
  ; REPRODUCED HERE, NOT INFERRED, before this was written. A minimal NSIS
  ; installer with the identical bare `File "helloim.ai.exe"` this used to be,
  ; run silently under Wine against a genuinely running, locked target, on
  ; this box: every run, exit 0, the file byte-for-byte unchanged. `IfErrors`
  ; DID catch it -- NSIS sets its own error flag on a failed overwrite even in
  ; silent mode -- it just does not stop the script or the exit code on its
  ; own, and this section never checked. That was the whole bug: not a slow
  ; file lock, a check that was never written.
  ;
  ; NOT FIXED WITH A LONGER SLEEP. The kill loop above already retries with
  ; backoff; the failure Beck found is the OS's own brief delay between a
  ; process disappearing from `tasklist` and it actually releasing the last
  ; handle on its own image file. A longer wait narrows that window, never
  ; closes it -- it would fail differently, at a different rate, on a
  ; different machine, exactly what she warned against.
  ;
  ; THE FIX SIDESTEPS THE RACE INSTEAD OF OUTRUNNING IT. Rename the running
  ; exe out of the way before writing the new one under its old name, rather
  ; than overwriting it in place. Windows opens an executing image with
  ; delete-sharing so the loader itself can still rename or delete it while it
  ; runs -- only overwriting its DATA is blocked -- and a same-directory
  ; rename is a directory-entry operation, not a data write, so it needs none
  ; of the lock the old direct overwrite was fighting. PROVEN, not assumed:
  ; the identical rename-then-write pattern, against the SAME still-running,
  ; still-locked target that had just failed the direct overwrite above, six
  ; runs in a row, six clean replacements -- the running process never even
  ; noticed, because it is still executing off the renamed file by handle,
  ; not by name.
  ;
  ; A leftover .old from an update whose old process outlived even ITS OWN
  ; rename step (rare, but the point of this comment is not to assume rare
  ; means never) is cleaned up here, best-effort -- if it is still locked,
  ; this Delete silently does nothing and the next update tries again.
  Delete "$INSTDIR\helloim.ai.exe.old"

  FileWrite $9 "reached SetOutPath + rename block$\r$\n"

  StrCpy $R9 0 ; $R9: "did a prior helloim.ai.exe actually exist" -- read below
  IfFileExists "$INSTDIR\helloim.ai.exe" 0 nameos_no_prior
    StrCpy $R9 1
    FileWrite $9 "prior helloim.ai.exe FOUND -- renaming out of the way$\r$\n"
    Rename "$INSTDIR\helloim.ai.exe" "$INSTDIR\helloim.ai.exe.old"
  nameos_no_prior:
  FileWrite $9 "about to File helloim.ai.exe$\r$\n"
  ; Errors from the Rename above are not checked here on purpose. If it
  ; failed, helloim.ai.exe is still sitting under its own name, and the File
  ; instruction below attempts the direct overwrite exactly as before --
  ; either it succeeds (nothing was actually wrong) or it fails, and THAT
  ; failure is what the check below exists to catch. One real check, not two.
  ;
  ; **RETRIED WITH BACKOFF, added 2026-09-04 -- this used to be ONE attempt,
  ; and reproducing the fresh-install ship-blocker under Wine on this box
  ; showed the SAME logic (unchanged since the working build hours earlier)
  ; flipping between a clean install and this exact Abort, run to run, with
  ; nothing else different.** That is the signature of a RACE, not a fixed
  ; bug -- and this file already has a proven fix for exactly that shape of
  ; race, in the kill loop above: retry with backoff rather than a single
  ; longer wait, because a longer wait narrows a race's window without
  ; closing it (see that loop's own comment). Applied here to the ONE case
  ; the earlier fix (rename-then-write) does not cover: THIS install's OWN
  ; first-ever write, where there is nothing running yet to rename around --
  ; the leading suspect for what holds it, unconfirmed without a real
  ; Windows box, is Defender/antivirus real-time scanning a brand-new,
  ; previously-unseen, unsigned executable the instant it lands on disk.
  ; 6 attempts, 500ms apart -- 3 seconds of headroom, well under what a
  ; silent installer can spend on one file without looking hung, and well
  ; past the sub-second window Beck already measured for the SAME class of
  ; lock in the update path above.
  StrCpy $R5 0
  nameos_write_retry:
    ClearErrors
    File "helloim.ai.exe"
    System::Call "kernel32::GetLastError()i.r8"
    FileWrite $9 "File helloim.ai.exe attempt $R5, GetLastError=$8$\r$\n"
    IfErrors 0 nameos_write_ok
    IntOp $R5 $R5 + 1
    IntCmp $R5 6 nameos_write_failed nameos_write_wait nameos_write_failed
    nameos_write_wait:
      Sleep 500
      Goto nameos_write_retry
  nameos_write_failed:
    FileWrite $9 "TAKING nameos_write_failed BRANCH AFTER $R5 ATTEMPTS -- WILL ABORT$\r$\n"
    FileClose $9
    ; THE REGISTRY MUST NEVER SAY MORE THAN THE DISK DOES. Everything past
    ; this point in this section -- DisplayVersion, the shortcuts, the
    ; relaunch -- runs only on a build that is actually on disk. Aborting
    ; here, before any of it, is what stops this becoming the exact lie Beck
    ; found: a version number that updated and a binary that didn't.
    ;
    ; RESTORE, DON'T JUST GIVE UP -- a machine left with no helloim.ai.exe at all
    ; (rename succeeded, the fresh write then failed for some unrelated
    ; reason -- disk full, an AV lock on the new bytes specifically) would be
    ; a worse outcome than the bug this exists to fix: that one at least left
    ; a working, if outdated, install. Best-effort, in order: clear away
    ; anything the failed write left half-written, then put the renamed
    ; original back under its real name -- ONLY IF THERE WAS ONE. $R9,
    ; recorded above, is what tells a genuine fresh-install failure (nothing
    ; to restore, and the OLD MESSAGE HERE, "could not be replaced," was
    ; simply wrong for this case -- there was nothing to replace) apart from
    ; an update failure (something real ends up put back).
    StrCmp $R9 0 nameos_write_failed_fresh
      Delete "$INSTDIR\helloim.ai.exe"
      Rename "$INSTDIR\helloim.ai.exe.old" "$INSTDIR\helloim.ai.exe"
      ; Exit code 2, verified on this box under Wine: `Abort` in silent mode
      ; sets this and returns immediately with no dialog -- there is nobody
      ; to click one during a silent update, same reasoning as .onInit
      ; above. The updater (tauri-plugin-updater) reads a non-zero exit as a
      ; failed install and will not tell anyone this succeeded.
      Abort "helloim.ai.exe could not be replaced -- it is still in use."
    nameos_write_failed_fresh:
      ; Same exit code, same silent-Abort reasoning -- see immediately
      ; above -- but a HONEST sentence for a fresh install, where nothing
      ; was ever being replaced: something else held the new file down
      ; long enough that even 3 seconds of retrying did not clear it.
      Abort "helloim.ai.exe could not be written -- something else on this PC has it locked."
  nameos_write_ok:
  FileWrite $9 "write_ok, proceeding to install the rest$\r$\n"
  FileClose $9
  ; Try to tidy up the renamed-away original right away too, in case its
  ; process had already exited by the time we got here. Best-effort, same as
  ; the Delete above -- a failure here means only that .old waits for the
  ; next run to clear it.
  Delete "$INSTDIR\helloim.ai.exe.old"

  ; The natural voices run through the ONNX runtime, which is linked into the
  ; exe -- but it pulls in DirectML, and that one is a DLL. Without this line
  ; the app does not start at all on any machine, and it looks like a corrupt
  ; download rather than a missing file.
  File "DirectML.dll"

  ; THE VC++ RUNTIME, APP-LOCAL -- Beck's SECOND NO-GO, 2026-09-05, reversing
  ; the chained-install approach that was here first. The exe has ordinary
  ; (non-delay) imports on MSVCP140.dll, MSVCP140_1.dll, VCRUNTIME140.dll and
  ; VCRUNTIME140_1.dll (read off its import table, not assumed), and a clean
  ; Windows 11 has none of them: the process cannot even be created, no
  ; window, nothing for startup.rs's own fatal-dialog fallback to catch,
  ; because the loader fails before main() runs at all.
  ;
  ; `-C target-feature=+crt-static` was tried first and rejected on real
  ; evidence: it fails to LINK under cargo-xwin, because `ort-sys`'s bundled
  ; ONNX Runtime objects expect a dynamically-linked CRT.
  ;
  ; CHAINING vc_redist.x64.exe AT INSTALL TIME WAS TRIED SECOND, AND SHIPPED,
  ; AND FAILED ON THE PRISTINE VM. vc_redist.x64.exe is manifested
  ; `requireAdministrator` -- Microsoft builds every version of it that way,
  ; it is not something a command-line flag turns off -- and this installer
  ; is deliberately `RequestExecutionLevel user` (see the block near the top
  ; of this file, Mark 2026-08-27: "don't ask for all those permissions just
  ; put them in play"). The `ExecWait` raised a UAC prompt on the secure
  ; desktop with nobody there to answer it: 776 seconds stuck, zero msiexec
  ; processes ever started, and the install died mid-Section leaving 182 MB
  ; on disk with no Uninstall.exe, no ARP entry, no shortcuts -- worse than
  ; doing nothing. The `IfSilent` branch built to keep a quiet/update install
  ; from blocking on that same dialog made it worse, not safer: it would have
  ; let the updater report success for an app that still cannot open a
  ; window, the exact silent-failure shape this whole pass exists to close.
  ;
  ; SO: NO INSTALLER, NO ELEVATION, NO SILENT SWALLOW. The four DLLs (plus
  ; the related CRT files below, extracted from the SAME redistributable) are
  ; staged beside helloim.ai.exe exactly the way DirectML.dll is, one line up
  ; -- an ordinary per-user file copy, nothing to consent to. Windows always
  ; searches the application's own directory for an imported DLL before
  ; anywhere else, so this satisfies the exact same non-delay imports that
  ; sent an installer-level fix down the wrong road twice.
  ;
  ; WHERE THESE FILES COME FROM: extract-vcrt.py, run by ship-windows.sh,
  ; pulls them out of the same vc_redist.x64.exe this file used to chain --
  ; it is a WiX Burn bundle with the real x64 "Minimum" and "Additional"
  ; runtime payloads embedded as nested cabinets, never installed or run,
  ; only unpacked. Redistributing these files app-local, beside the exe that
  ; needs them, is a use Microsoft's own docs describe directly, on the same
  ; page already cited for the rejected chain -- "Install individual
  ; redistributable files" ("It's also possible to directly install the
  ; Redistributable DLLs in the application local folder"):
  ;   https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files
  ; THE TRADE THAT PAGE NAMES, AND THE REASON IT CALLS THIS THE SECONDARY
  ; OPTION: an app-local copy does not get patched by Windows Update the way
  ; a machine-wide install does. Noted, not solved here -- these are the same
  ; four files a fresh vc_redist.x64.exe download always carries, so the fix
  ; is re-running ship-windows.sh, the same as any other bundled dependency.
  File "vcrt\concrt140.dll"
  File "vcrt\msvcp140.dll"
  File "vcrt\msvcp140_1.dll"
  File "vcrt\msvcp140_2.dll"
  File "vcrt\msvcp140_atomic_wait.dll"
  File "vcrt\msvcp140_codecvt_ids.dll"
  File "vcrt\vcruntime140.dll"
  File "vcrt\vcruntime140_1.dll"

  ; STEP 1 DONE, STEP 2 ACTIVE. Everything up to this line -- the kill loop,
  ; the rename-then-write dance, helloim.ai.exe and DirectML.dll -- is "setting up
  ; helloim.ai" in the sense a person watching the page would mean it.
  ;
  ; "DONE" is a COLOUR change, not new text -- step 1's filled-circle glyph
  ; already says "under way"/"complete" is the same glyph, told apart by the
  ; accent colour alone, so there is only the SetCtlColors call and no second
  ; string to keep in sync with the active one. InvalidateRect is required
  ; here specifically: SetCtlColors only updates the colour NSIS hands back on
  ; the NEXT WM_CTLCOLORSTATIC, it does not itself trigger a repaint, and
  ; unlike step 2 below (whose text is also changing, which repaints on its
  ; own) step 1's text is not changing here -- without this call the colour
  ; would sit correct-but-invisible until something else forced the window to
  ; redraw.
  SetCtlColors $NameOS_Step1 "${NAMEOS_ACCENT}" "${MUI_BGCOLOR}"
  System::Call 'USER32::InvalidateRect(p $NameOS_Step1, p0, i1)'
  SendMessage $NameOS_Step2 ${WM_SETTEXT} 0 "STR:${NAMEOS_STEP2_ACTIVE}"
  SetCtlColors $NameOS_Step2 "${NAMEOS_INK}" "${MUI_BGCOLOR}"
  ; THE ONE CAPTION SWAP THIS SECTION KEEPS -- gated on PROGRESS REMAINING,
  ; not on the clock. See the design note above (where NameOS_MaybeAdvance-
  ; Caption used to sit) for why timing this checkpoint failed twice.
  ;
  ; $mui.InstFilesPage.ProgressBar is the SAME control this file already
  ; colours a few dozen lines up -- PBM_GETPOS/PBM_GETRANGE are answered by
  ; NSIS's own core exactly like PBM_SETBARCOLOR/PBM_SETBKCOLOR are received
  ; by it, so this is reading the identical live signal the visible bar is
  ; drawn from, not a second, separate estimate of progress that could
  ; disagree with what the user is looking at.
  ;
  ; wParam=TRUE(1) returns the low limit, wParam=FALSE(0) the high limit,
  ; lParam=0 so each call returns the single value directly rather than
  ; filling a PBRANGE struct -- both per Microsoft's own PBM_GETRANGE and
  ; PBM_GETPOS references (learn.microsoft.com/windows/win32/controls/
  ; pbm-getrange and .../pbm-getpos). The plain NSIS `SendMessage` instruction
  ; captures an integer return straight into a var (nsis.sourceforge.io/
  ; Reference/SendMessage) -- no System::Call needed here, unlike WM_GETFONT
  ; above, because these returns are plain values, not pointers.
  SendMessage $mui.InstFilesPage.ProgressBar ${PBM_GETPOS} 0 0 $R6
  SendMessage $mui.InstFilesPage.ProgressBar ${PBM_GETRANGE} 1 0 $R7
  SendMessage $mui.InstFilesPage.ProgressBar ${PBM_GETRANGE} 0 0 $R8
  IntOp $R9 $R8 - $R7                    ; total = high - low
  ; FAILS CLOSED: a zero or negative range means the read could not be
  ; trusted (control not ready, or a call that did not land), and the
  ; instruction was explicit that this must mean "do not swap", never
  ; "assume plenty is left and swap anyway". Leaving caption 1 up is always
  ; the safe wrong answer; a second caption truncated to nothing is not.
  IntCmp $R9 0 nameos_c2_skip nameos_c2_skip nameos_c2_range_ok
  nameos_c2_range_ok:
    ; THE THRESHOLD: about half. Chosen because it is exactly what was asked
    ; for, it needs no invented constant, and it means a swap only ever
    ; happens when caption 2 is inheriting the MAJORITY of whatever
    ; installed-byte progress is left -- the closest this checkpoint can get,
    ; without trusting wall-clock time at all, to "caption 2 gets the rest of
    ; the install" rather than a sliver of it.
    IntOp $R9 $R9 / 2                    ; half of total
    IntOp $R8 $R8 - $R6                  ; remaining = high - pos (reuses $R8)
    ; remaining >= half -> at most half done, worth swapping into.
    ; remaining <  half -> MORE than half already done, leave caption 1 up.
    IntCmp $R8 $R9 nameos_c2_check_dwell nameos_c2_skip nameos_c2_check_dwell
  nameos_c2_check_dwell:
    ; THE 2.5s DWELL FLOOR STAYS, AS A SECOND, INDEPENDENT GATE -- both this
    ; and the progress check above must pass. Progress-remaining says there is
    ; probably enough install left to be worth swapping into; this says
    ; caption 1 has actually had a moment on screen first. Same constant the
    ; deleted dwell-gate function used, kept rather than re-picked.
    System::Call 'KERNEL32::GetTickCount() i.r0'
    IntOp $1 $0 - $NameOS_CaptionTick
    IntCmp $1 2500 nameos_c2_swap nameos_c2_skip nameos_c2_swap
  nameos_c2_swap:
    SendMessage $NameOS_Caption ${WM_SETTEXT} 0 "STR:${NAMEOS_CAPTION_2}"
    StrCpy $NameOS_CaptionTick $0
  nameos_c2_skip:

  ; THE NATURAL VOICES, IN THE BOX. Mark, 2026-08-26: "can we package this into
  ; our installer so they dont have to go and download." A 115 MB download
  ; standing between somebody and the good voices is a step most people never
  ; take, and the ones who would take it are not who this is for.
  ;
  ; They go in the PROGRAM directory, not each user's profile: the files are
  ; read-only and shared, and copying 115 MB per person for something nobody
  ; edits is waste that turns up as a full disk months later. tts.rs looks in
  ; the per-user folder first, so anyone who downloads a newer model still
  ; overrides this copy rather than being silently overruled by it.
  SetOutPath "$INSTDIR\tts"
  File "tts\kokoro.onnx"
  File "tts\voices.bin"
  SetOutPath "$INSTDIR"

  ; STEP 2 DONE, STEP 3 ACTIVE. The 115 MB voice pack is the slow part of this
  ; whole section on a spinning disk, which is also exactly why it is the step
  ; most worth a line of its own rather than folding it into step 1.
  ; Same colour-not-text DONE mechanism as step 1 above -- see its comment.
  SetCtlColors $NameOS_Step2 "${NAMEOS_ACCENT}" "${MUI_BGCOLOR}"
  System::Call 'USER32::InvalidateRect(p $NameOS_Step2, p0, i1)'
  SendMessage $NameOS_Step3 ${WM_SETTEXT} 0 "STR:${NAMEOS_STEP3_ACTIVE}"
  SetCtlColors $NameOS_Step3 "${NAMEOS_INK}" "${MUI_BGCOLOR}"
  ; NO CAPTION SWAP ATTEMPT HERE -- deliberately out of scope, not measured
  ; and rejected. This checkpoint fires once the whole voice-pack copy has
  ; already finished, so on almost any machine there is little of the install
  ; left behind it -- the exact shape the progress gate above exists to
  ; refuse. Adding a second progress-gated attempt here was considered and
  ; left undone: whatever is on screen by this point (caption 1 or 2,
  ; depending on what the checkpoint above decided) already has whatever
  ; dwell it is going to get, and this file only carries one swap site at a
  ; time on purpose -- see the design note above NameOS_MaybeAdvanceCaption.

  ; WebView2 runtime — the app renders through it. Only install it if it's
  ; genuinely MISSING. Running the bootstrapper when it's already present is
  ; what hung the installer on the "Checking the WebView2 runtime" step, so we
  ; check the registry first (system-wide, then per-user) and skip if found.
  ;
  ; THE REGISTRY SPELLING IS CORRECT AND IS NOT DOUBLE-REDIRECTED — VERIFIED ON
  ; A REAL WINDOWS 11 MACHINE, 2026-08-28, not reasoned about. This installer is
  ; a 32-bit process, and the standing worry with a 32-bit process reading an
  ; explicit `WOW6432Node` path is that WOW64 redirection turns it into
  ; `WOW6432Node\WOW6432Node` and it silently finds nothing — which would mean
  ; running the bootstrapper on every install forever, the exact hang the check
  ; above was added to stop. `reg query <literal path> /reg:32` and
  ; `reg query <unqualified path> /reg:32` both returned pv 151.0.4129.107 on
  ; that machine, so the two spellings resolve to the same key. DO NOT "fix"
  ; this path.
  ;
  ; WHAT WAS WRONG, and Microsoft documents it: a present-but-EMPTY `pv`, and a
  ; `pv` of "0.0.0.0", both mean the runtime is NOT installed. The old check was
  ; `StrCmp $0 "" 0 wv2_present` — anything non-empty counted as present, so a
  ; machine reporting 0.0.0.0 was declared fine, the bootstrapper never ran, and
  ; the app it installed could never open a window. That is the customer-facing
  ; failure this whole pass is about, reached through the installer instead of
  ; through the app.
  ;   https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution
  DetailPrint "Checking the WebView2 runtime…"
  ReadRegStr $0 HKLM "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  StrCmp $0 "" wv2_try_hkcu
  StrCmp $0 "0.0.0.0" wv2_try_hkcu
  Goto wv2_present
  wv2_try_hkcu:
  ReadRegStr $0 HKCU "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  StrCmp $0 "" wv2_install
  StrCmp $0 "0.0.0.0" wv2_install
  Goto wv2_present

  wv2_install:
    DetailPrint "WebView2 not found — installing it…"
    SetOutPath "$TEMP"
    File "MicrosoftEdgeWebview2Setup.exe"
    ; THE EXIT CODE IS READ NOW, AND IT USED TO BE THROWN AWAY. This is the
    ; ONLINE bootstrapper: it downloads the runtime, so it fails on a machine
    ; with no internet, behind a proxy that blocks it, or under a policy that
    ; forbids the install. Every one of those ended with a green "installation
    ; complete" and an app that opens nothing — a failure the person has no way
    ; to attribute, because the step that failed reported success.
    ExecWait '"$TEMP\MicrosoftEdgeWebview2Setup.exe" /silent /install' $1
    Delete "$TEMP\MicrosoftEdgeWebview2Setup.exe"
    StrCmp $1 "0" wv2_done
      DetailPrint "WebView2 install FAILED (exit $1)."
      ; NOT DURING A SILENT UPDATE. Same rule as `.onInit` at the top of this
      ; file: there is no window for a dialog to appear over and nobody to click
      ; it, so it would wait forever on a machine the person thinks is idle. The
      ; DetailPrint above still records it, and the app now writes its own line
      ; when it cannot start (src/startup.rs).
      IfSilent wv2_done
      MessageBox MB_OK|MB_ICONEXCLAMATION \
"${APP} is installed, but the Microsoft Edge WebView2 Runtime could not be \
installed alongside it.$\r$\n$\r$\n\
${APP} draws its window with WebView2, so it will not open until that is \
fixed. This usually means no internet connection during setup.$\r$\n$\r$\n\
Get it from https://developer.microsoft.com/microsoft-edge/webview2/ and then \
start ${APP} — nothing here needs redoing."
    Goto wv2_done
  wv2_present:
    DetailPrint "WebView2 already installed ($0) — skipping."
  wv2_done:
  ; PUT THE OUTPUT DIRECTORY BACK. `SetOutPath "$TEMP"` above is still in force
  ; on the path that ran the bootstrapper, and `CreateShortcut` takes its "Start
  ; in" folder from wherever SetOutPath last pointed — so the shortcuts made
  ; below would have said %TEMP% for exactly the people who needed WebView2
  ; installed, and $INSTDIR for everybody else. Two different installs from one
  ; installer, differing only by a branch nobody tests.
  SetOutPath "$INSTDIR"

  ; STEP 3 DONE, STEP 4 ACTIVE. WebView2 is a machine-level check, not
  ; something particular to this copy of helloim.ai -- but it is real work this
  ; installer actually does, and the wv2_install branch above can take a real
  ; few seconds fetching the runtime, so it earns its own row rather than being
  ; silently folded into "finishing up."
  ; Same colour-not-text DONE mechanism as step 1 above -- see its comment.
  SetCtlColors $NameOS_Step3 "${NAMEOS_ACCENT}" "${MUI_BGCOLOR}"
  System::Call 'USER32::InvalidateRect(p $NameOS_Step3, p0, i1)'
  SendMessage $NameOS_Step4 ${WM_SETTEXT} 0 "STR:${NAMEOS_STEP4_ACTIVE}"
  SetCtlColors $NameOS_Step4 "${NAMEOS_INK}" "${MUI_BGCOLOR}"
  ; NO CAPTION SWAP HERE EITHER -- later still than the checkpoint above, so
  ; the same reasoning applies harder. See the design note above
  ; NameOS_MaybeAdvanceCaption.

  ; Shortcuts — Start menu + Desktop, like any real app.
  ;
  ; NOT RE-CREATED BY AN UPDATE. Somebody who deleted the desktop icon has said
  ; what they want, and an app that puts it back every time it updates is the
  ; behaviour everybody hates in other people's software. A first install still
  ; gets both.
  StrCmp $IsUpdate 1 skip_shortcuts
    CreateDirectory "$SMPROGRAMS\${APP}"
    CreateShortcut "$SMPROGRAMS\${APP}\${APP}.lnk" "$INSTDIR\helloim.ai.exe"
    CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\helloim.ai.exe"
  skip_shortcuts:

  ; Register for Add/Remove Programs + write the uninstaller.
  WriteRegStr HKCU "Software\${APP}" "InstallDir" "$INSTDIR"
  ; Written here, where $APPDATA is still the installing user's, so the
  ; uninstaller does not have to guess whose profile to clean.
  WriteRegStr HKCU "Software\${APP}" "ConfigDir" "$APPDATA\${IDENT}"
  ; DISPLAYNAME IS THE BARE APP NAME, NOT "${APP} ${VERSION}" -- checked
  ; against helloim.ai's package.json (uninstallDisplayName: "helloim.ai
  ; ${version}") and deliberately not copied. DisplayVersion, written on the
  ; very next line, already puts the number in Add/Remove Programs' own
  ; Version column -- folding it into the Name column too would just repeat
  ; it next to itself. Nothing here reads DisplayName expecting a version in
  ; it (the read-back on the next update, a few hundred lines up, keys off
  ; UninstallString and InstallLocation instead), so there is no behaviour
  ; riding on this staying bare either way -- it is a legible-list call, made
  ; and stated rather than left to look unconsidered.
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}" "DisplayName" "${APP}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}" "DisplayVersion" "${VERSION}"
  ; Without this the Publisher column is blank next to every other program
  ; on the machine, which reads as unsigned junk.
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}" "Publisher" "${COMPANY}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}" "DisplayIcon" "$INSTDIR\helloim.ai.exe"
  ; Read back by .onInit on the next update to find where helloim.ai actually lives.
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}" "InstallLocation" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; STEP 4 DONE. The short Sleep is deliberate -- without it the page can reach
  ; "Installation Complete" and swap to the Finish header before anyone's eye
  ; has landed on the fourth row turning accent-coloured, which would mean the
  ; row existed and nobody ever actually saw it finish. Skipped during a
  ; silent update: nobody is watching a page silent mode never shows, and it
  ; is real seconds on a step nobody chose to wait through.
  ; Same colour-not-text DONE mechanism as step 1 above -- see its comment.
  SetCtlColors $NameOS_Step4 "${NAMEOS_ACCENT}" "${MUI_BGCOLOR}"
  System::Call 'USER32::InvalidateRect(p $NameOS_Step4, p0, i1)'
  ; THIS USED TO ADVANCE THE CAPTION ONE LAST TIME, AND THAT WAS THE BUG --
  ; Beck's real-hardware measurement, 2026-08-29: reproducible to within 20ms
  ; across two runs, the caption showing at THIS checkpoint held only 1.07s
  ; and 1.05s before the page changed out from under it, against 8.2s/8.3s for
  ; the one before it. The dwell gate in NameOS_MaybeAdvanceCaption protects a
  ; caption from being overwritten too SOON; it has no way to know this is the
  ; last checkpoint there will ever be, so whatever it swapped to here was
  ; always going to be cut off by Section "helloim.ai" simply ending.
  ;
  ; THAT FIX WAS RIGHT AND IT WAS NOT ENOUGH -- Beck's recheck, same day,
  ; found the checkpoint one BEFORE this one (Step2 Done / Step3 Active, ~7.8s
  ; in) had exactly the same problem for exactly the same reason: it also
  ; fires after the slow copy has already used up most of the install. Only
  ; removing the swap here left that one still cutting a caption short to
  ; ~1.06s, and still only two captions ever appeared. The real fix -- which
  ; checkpoints are allowed to swap the caption at all -- is the design note
  ; above NameOS_MaybeAdvanceCaption, not this comment; this one is kept for
  ; the history, since it is still true as far as it goes, just not the whole
  ; story on its own anymore.
  ;
  ; NAMEOS_CAPTION_3, 4 AND 5 are all unused now, not just 5. Same reasoning
  ; as this paragraph always gave for 5: each !define is left in place, real
  ; accurate copy, ready the moment there is ever a checkpoint with genuine
  ; dwell time to hang one on.
  ;
  ; AND NEITHER OF THOSE TWO FIXES WAS THE LAST ONE EITHER -- a third pass,
  ; same day: making the one remaining swap unconditional (on the theory it
  ; always fires early, before the slow copy) turned out to fire at 1.54s on
  ; this box's own wine rig and at roughly 7.8s on Beck's real hardware, same
  ; shape of failure as the two above wearing a new checkpoint. The swap is
  ; now gated on the progress bar's OWN remaining fraction instead of any
  ; clock -- see the design note above NameOS_MaybeAdvanceCaption, which is
  ; current; this whole comment is history, not the live rule.
  ;
  ; THE SLEEP BELOW IS UI-ONLY AND UNRELATED TO CAPTIONS -- it pauses for the
  ; step-list's own fourth row, timed AFTER every real file operation in this
  ; section has already completed, so it never blocks the copy thread. See
  ; NameOS_MaybeAdvanceCaption's own note for why nothing upstream of it may
  ; ever do the same.
  StrCmp $IsUpdate 1 +2
    Sleep 900

  ; START IT AGAIN, because the update closed it. The finish page normally does
  ; this and there is no finish page in a silent run -- so without this the app
  ; someone was using simply vanishes and they have to go and find the icon.
  ;
  ; VIA EXPLORER, NOT DIRECTLY, and that detail matters. This installer runs
  ; elevated; anything it launches inherits that, and helloim.ai would come back as
  ; administrator -- a browser engine, a webview profile and every file the
  ; assistant touches, all running with rights they were never meant to have,
  ; silently, from then until the next reboot. explorer.exe runs as the signed-in
  ; person, so handing it the path drops us back to their level.
  StrCmp $IsUpdate 0 +2
    Exec '"$WINDIR\explorer.exe" "$INSTDIR\helloim.ai.exe"'
SectionEnd

; UNINSTALL.
;
; The program files and registry entries were always removed correctly. What
; this section did NOT touch is the part that actually matters when somebody
; says "remove this from my machine": the settings folder, and the API keys
; sitting in Windows Credential Manager. Keys outliving the app that put them
; there is the wrong default -- a person who uninstalls a thing has said what
; they want.
;
; It ASKS rather than assuming, because the other reason people uninstall is to
; reinstall, and silently wiping someone's profile and connections in the middle
; of a repair would be its own kind of broken.
;
; NO customUnInit-STYLE HOOK WAS ADDED HERE, AND THAT WAS CHECKED, NOT
; ASSUMED. helloim.ai's build/installer.nsh runs a small cleanup macro
; (customUnInit) from Function un.onInit specifically because electron-
; builder's OWN installer silently re-invokes the OLD version's uninstaller
; as an internal step of every upgrade -- so it needs an ${isUpdated} guard
; to tell "the person is actually leaving" apart from "a newer Setup is
; quietly replacing this one", and it needs that guard checked before
; anything is deleted (un.onInit, not the delete-everything Section).
; helloim.ai has no equivalent internal step to guard against: Section "helloim.ai"
; above handles both a fresh install and a Repair/Update entirely on its
; own -- rename-then-write, re-register, done -- and NEVER calls this
; uninstaller, silently or otherwise. This Section now only ever runs from a
; direct run of Uninstall.exe via Windows Settings > Apps (or Add/Remove
; Programs) -- CORRECTED 2026-08-31: Setup.exe's own already-installed
; prompt used to offer "Uninstall" as one of three buttons and route straight
; into this Section from a labelled branch in .onInit. That branch is gone;
; see the prompt's own comment in .onInit for why (grep this file for
; "already installed on this PC" to find it). There
; is no "internal upgrade" case here to distinguish from a real one, so there
; is nothing for a guard to guard against.
;
; AND WHAT THAT HOOK CLEARS -- a session token and a launch-at-login entry,
; per uninstall-cleanup.js -- helloim.ai has no launch-at-login feature to clean
; up at all (grepped src-tauri for autostart/login-item, nothing there), and
; its equivalent of a session token is already the broader "connectors.json
; credential + WebView2 profile" wipe a few dozen lines down in this same
; Section, gated behind the prompt above rather than an always-on JS call.
; Same ground covered, different mechanism, already in place -- not a gap.
Section "Uninstall"
  ; READ THE CONFIG PATH FIRST, BEFORE ANYTHING IS DELETED. Found 2026-08-27.
  ; This was at the BOTTOM of the section, thirty lines below the
  ; `DeleteRegKey HKCU "Software\${APP}"` that removes the very value it reads
  ; -- so it always came back empty and always fell through to the fallback,
  ; which is `$APPDATA\${IDENT}` under an elevated uninstaller: the ADMIN's
  ; profile, not the profile of the person who used helloim.ai.
  ;
  ; The comment further down describes this exact trap and says the value is
  ; read back to avoid it. It was; it was just read too late to still exist.
  ; The result is the fault this whole block was written to fix, still live: a
  ; real user's settings, connector list and stored keys survive an uninstall,
  ; and a reinstall comes up already signed in.
  ReadRegStr $R0 HKCU "Software\${APP}" "ConfigDir"
  StrCmp $R0 "" 0 +2
    StrCpy $R0 "$APPDATA\${IDENT}"

  ; The voices are ours and they are 115 MB. Leaving them behind is the same
  ; fault as the loose helloim.ai.exe on the desktop: something the uninstaller
  ; put there that the uninstaller does not remove.
  Delete "$INSTDIR\tts\kokoro.onnx"
  Delete "$INSTDIR\tts\voices.bin"
  RMDir "$INSTDIR\tts"
  Delete "$INSTDIR\helloim.ai.exe"
  Delete "$INSTDIR\DirectML.dll"
  ; The app-local VC++ runtime files -- see the File block beside
  ; DirectML.dll above for why these are here instead of a machine-wide
  ; install. Nothing else on the machine owns them or expects them to
  ; persist; leaving them is the same "uninstaller doesn't remove what the
  ; installer put there" fault as the voices, above.
  Delete "$INSTDIR\concrt140.dll"
  Delete "$INSTDIR\msvcp140.dll"
  Delete "$INSTDIR\msvcp140_1.dll"
  Delete "$INSTDIR\msvcp140_2.dll"
  Delete "$INSTDIR\msvcp140_atomic_wait.dll"
  Delete "$INSTDIR\msvcp140_codecvt_ids.dll"
  Delete "$INSTDIR\vcruntime140.dll"
  Delete "$INSTDIR\vcruntime140_1.dll"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\${APP}\${APP}.lnk"
  RMDir "$SMPROGRAMS\${APP}"
  Delete "$DESKTOP\${APP}.lnk"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}"
  DeleteRegKey HKCU "Software\${APP}"

  ; THE WEBVIEW PROFILE, which the uninstaller used to leave behind entirely.
  ; Found 2026-08-26 when Mark asked for a clean slate before a fresh install:
  ; program files gone, both registry keys gone, shortcuts gone, credentials
  ; gone -- and 39.8 MB sitting in LOCALAPPDATA\${IDENT}\EBWebView.
  ;
  ; THAT FOLDER IS THE ONE THAT MAKES A "FRESH" INSTALL NOT FRESH. WebView2
  ; keeps localStorage there, which is where the sign-in token, the
  ; tour-already-seen flag and the voice choice live. Reinstall with it in
  ; place and the app comes up already signed in, skips the first-run tour,
  ; and behaves like the old install wearing new binaries -- so a first-run
  ; bug is invisible to the one person testing for it.
  ;
  ; IT USED TO RUN HERE, UNCONDITIONALLY, BEFORE THE PROMPT BELOW EVER ASKED
  ; -- Beck, build b15. She answered No to "Also remove your helloim.ai settings?
  ; ... Choose No if you are reinstalling and want to keep them" and watched
  ; this exact folder go from present to absent regardless: the sign-in
  ; token, the theme and the voice choice were gone before her answer could
  ; ever have mattered, because the delete already ran above the question.
  ; There is no reading of that promise under which the sign-in token is
  ; exempt from it -- a person reinstalling who wants to keep their settings
  ; means all of them, this folder included. So the fix is the ORDER, not the
  ; wording: this block now runs from inside the "Yes, remove them" branch,
  ; a few lines down, instead of before that branch even exists. The
  ; prompt's own wording already said the right thing; the code just was not
  ; doing it -- and the wording is widened below to say so honestly, now
  ; that it is true.
  ;
  ; $LOCALAPPDATA, like $APPDATA, points at the ADMIN's profile under an
  ; elevated uninstaller, so it is derived from the recorded config dir rather
  ; than read directly.
  ; $R0 is the config dir, read at the top of this section -- see the note
  ; there for why it cannot be read here.
  ;
  ; AND IT IS GUARDED, because the instruction below is a recursive delete
  ; built from a path out of the registry. If $R0 were ever empty, GetParent
  ; twice would leave "" and this would recurse from the root of the current
  ; drive. That is the one mistake in this file that could not be apologised
  ; for, so it refuses to run on anything that is not an absolute path.

  IfFileExists "$R0\*.*" 0 done
    MessageBox MB_YESNO|MB_ICONQUESTION \
      "Also remove your ${APP} settings?$\r$\n$\r$\nThis deletes your sign-in, your About you profile, your connection list, your theme and voice choice, and any API keys ${APP} stored in Windows Credential Manager.$\r$\n$\r$\nChoose No if you are reinstalling and want to keep them." \
      /SD IDNO IDNO done

    ${GetParent} "$R0" $R2          ; ...\AppData\Roaming
    ${GetParent} "$R2" $R2          ; ...\AppData
    StrCpy $R3 "$R2" 2              ; expect a drive letter and a colon
    StrCmp $R3 "" no_webview
    StrCpy $R3 "$R2" 1 1
    StrCmp $R3 ":" 0 no_webview
    IfFileExists "$R2\Local\${IDENT}\*.*" 0 no_webview
      RMDir /r "$R2\Local\${IDENT}"
    no_webview:

    ; The keys first, while connectors.json still exists to name them. The
    ; keyring crate stores each one under "<connector id>.NameOS", so the ids
    ; in that file are exactly the credentials to remove.
    ;
    ; HARDCODED "NameOS", NOT ${APP} -- deliberate, as of the helloim.ai rename.
    ; `KEYRING_SERVICE` in connectors.rs/providers.rs was left as the literal
    ; string "NameOS" on purpose (renaming it would orphan every credential a
    ; user already has stored — see the rename's own report). ${APP} is now
    ; "helloim.ai", so following it here would search Credential Manager for
    ; entries that were never written under that suffix and leave the real
    ; ones behind on uninstall. If KEYRING_SERVICE is ever renamed, change the
    ; literal below to match it — the two are not linked by the compiler the
    ; way IDENT and the app's identifier are, so nothing will warn you.
    nsExec::ExecToLog 'cmd /c for /f "tokens=2 delims=:, " %A in ('findstr /i "\"id\"" "$R0\connectors.json"') do @for /f "tokens=* delims=\"" %B in ("%~A") do @cmdkey /delete:%~B.NameOS'
    Pop $R1
    RMDir /r "$R0"
  done:
SectionEnd
