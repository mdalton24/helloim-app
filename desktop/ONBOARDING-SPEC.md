# NameOS first-run onboarding — the base questions

**Mark's instruction, 2026-08-26: after initial install, ask base questions to
set the average person up — who they are and what they want — and produce an
initial setup INCLUDING seed notes. "We need not to assume."** Every question
below exists because the alternative is assuming something. Seed notes are the
output that also solves the empty-brain problem: the graph is populated from the
first open.

Keep it short and human — the average person, not a power user. Clickable options
over blank boxes wherever possible. Runs once, after install, before the main app.

## The six questions

1. **Name it.** "What do you want to call your assistant?"
   → the product hook; makes it theirs from the first screen. Free text, offer a
   suggestion or two. This is the "give it a name" moment.

2. **Who you are.** "What best describes you?" — Developer/Engineer · Creator or
   content maker · Business owner or freelancer · Writer · Student or researcher ·
   Something else.
   → tailors which crew/specialists show first and the language used. **Do not
   assume they're technical.**

3. **What you want to do with it.** "What do you mainly want a hand with?" —
   Writing & content · Coding & building · Research & learning · Organizing my
   notes & projects · Running my business · Just exploring.
   → drives the initial crew + which seed notes to create. "Just exploring" is a
   real option — don't force a goal.

4. **The first real thing.** "What's one thing on your plate right now you'd want
   help with?" — free text.
   → becomes their FIRST seed note/project, so the brain has real content from
   note one and the first session starts on something concrete, not a blank prompt.
   This is the anti-empty-brain move.

5. **How much rope.** "How much should it do on its own before checking with
   you?" — Ask me first (safest) · Let it edit files, ask before bigger things ·
   Full speed, I'll watch.
   → sets the permission-mode default. **Never assume they want autonomy.**

6. **Where it lives.** "Where should it keep your notes and work?" — Pick a folder
   · Create one for me.
   → sets up a real vault so the brain has a home and never opens on an empty
   drive root.

## What the answers produce (the initial setup)

- A **named assistant** (Q1).
- A **crew tuned to them** — which specialists surface first (Q2 + Q3).
- The **permission-mode default** (Q5).
- A **working folder/vault**, created if they chose "create one for me" (Q6).
- **Seed notes written into the vault**, so the brain glows on first open:
  - a **Welcome, [name]** / "Start here" note,
  - a note capturing **the thing on their plate** (Q4) as their first project,
  - a short **"What your crew does"** note tuned to Q2/Q3.

## A seventh step, added 2026-08-28 — not one of Mark's six

**"In your own words," `~/Documents/Iris/2026-08-28-persona-interview-placement.md`
+ `~/Documents/Cyrus/2026-08-28-persona-questions.md`.** The eleven-question
voice interview lives as a fourth Profile tab, not here — the reasoning is in
Iris's file (the payoff cannot exist at first run, and this wizard already
drew blood three times in one day). What DID land in the wizard is one extra
step, carrying three of Vera's zero-thought preference questions as pills
(sentence pace, serious/funny, warm/blunt), because those need no recall, no
judgement and no disclosure. It writes into the same "How should I be?" field
Q1–Q3 already ride into `CLAUDE.md`, never overwriting something already typed.
It is the seventh and last step; `STEPS.length` drives the step count and dot
row, so nothing here was hardcoded to six.

## Build notes

- Lives in `desktop/ui/index.html` (single file). Queues AFTER the brain/ambient
  work and the voice work — same file, one editor at a time.
- Runs once; gate it on a stored flag (e.g. `localStorage nameos_onboarded` or a
  marker file in the chosen vault). "New conversation" is not re-onboarding.
- The seed-note WRITING is real: create actual `.md` files in the chosen folder so
  the vault (and the brain) is genuinely populated — honest, not a mock.
- Honesty: don't over-promise the crew. Only name specialists the shipping app
  actually exposes today; frame the rest as coming.
