# NameOS — UX/UI findings, 2026-08-27

Mark's brief, 2026-08-26 late: *"research best ux/ui skill to redesign the nameos
application interface and website to match and be user friendly even if that
means moving icons around .. we needs to also look at our competition and see
what things we are missing as they still look more polished. Put it together and
summary email for me by morning."*

The summary went by email (id `1a04195d00a1f5a1`). This is the long version it
referred to — **written after the fact, because the email promised "full findings
are on the machine" and there was no file. That was a promise made and not kept
until Mark asked where it was.**

Two decisions are waiting on him and nothing below should be built before they
are answered:

1. **Which accent do we standardise on** — the site's mint, or the app's blue?
2. **Do we use the real vendor logos** instead of coloured letters?

**No code was changed.** He asked for research and a summary.

---

## 1. The skill

**Recommendation: `szilu/ux-designer-skill`.** MIT, 52 stars, pushed 2026-08-14,
`SKILL.md` is 17,824 bytes with 26 reference files. Verified twice — once by the
specialist, once by me directly against the GitHub API and the raw file.

**Zero dependencies.** Grepped for npm, node, react, tailwind, figma: nothing but
one blog link. It is a plain skill, copied by hand the same way
`design-taste-frontend` already was — never through an `npx` installer.

**Why this one.** "User friendly even if that means moving icons around" is an
information-architecture and findability problem, not a visual-taste problem. It
is the only candidate built for that, and it carries
`05-information-architecture.md` and `06-interaction-design.md` as references. Its
own description names **voice and AI interfaces**, which is exactly what NameOS
is.

**What we already have.** `~/.claude/skills/design-taste-frontend` (from
`Leonxlnx/taste-skill`, MIT, provenance on file). It is good and it stays — it
handles how a thing looks once the layout is settled. The two complement rather
than compete. Run the new one first, that one second.

**Also worth adding later:** `vercel-labs/web-interface-guidelines` — 811 stars,
MIT, ships as a plain markdown slash command with no npm on the Claude Code path.
About 150 checkable rules (focus states, hit targets, forms, animation). Good as
a final "did we ship it clean" pass.

**Rejected, so nobody re-finds them:**

| Candidate | Why not |
|---|---|
| `plugin87/ux-ui-agent-skills` | Node/npm package, ships an MCP server needing a **paid Figma key**, targets React/Tailwind/Vue. Wrong stack, and it is the runtime wall Mark ruled out. |
| `nextlevelbuilder/ui-ux-pro-max-skill` | Real project, but its engine is a TypeScript CLI needing Node. Also claims 121k stars for a year-old niche skill, which is not plausible and was not verifiable. |
| Anthropic's `frontend-design` | Legitimate, but duplicates the taste skill we already have. Adds nothing to *this* brief. |
| `content-designer/ux-writing-skill` | Real but narrow; already covered by szilu's own `09-ux-writing.md`. |
| Composio `brandfetch` / `canvas` / `composio` automations | All need the Rube MCP connector plus a paid third-party connection. Same refusal as the subscription connector removed on 2026-08-26. |
| `brand-guidelines`, `canvas-design`, `theme-factory` (in toddaerickson/claude-skills) | Not UX skills — brand colours, generative posters, slide themes. |
| `webapp-testing` | Playwright test kit. Useful to *verify* a redesign renders, not to produce one. |

The `composio-skills` tree in that repository — roughly 700 entries — is entirely
service-integration automations behind a paid connector. There is **no real UX/UI
skill in there at all.**

---

## 2. The competition

### The finding that reframes everything

**ZoeyOS publish no screenshots of their app. Anywhere.** No public interface
shots, the explainer says *"Demo video coming soon,"* and the download is
subscription-gated.

So the thing we have been comparing ourselves against is **their website, not
their product.** Their site is finished. Ours shows no picture of the product at
all.

We are not losing to a better interface. We are losing to better presentation of
an interface nobody outside has seen.

### Ranked gaps, most damaging first

**1. Our first frame is an error; theirs is a capability.**
The chat panel opens on *"Microphone access was blocked. Allow it for NameOS,
then click the mic."* No button, no link to settings, no way to fix it from where
it is shown. Raycast, Jan and LM Studio all open on the product doing something.
The good state already exists in our own build (`shots/voicebar.png`) — it simply
is not what a blocked mic falls back to. Lives in the chat-panel empty state in
`desktop/ui/index.html`.

**2. The app and the site are two different products, in look and in claim.**
Verified directly — **not one shared colour token:**

| | Site (`desktop/site/index.html`) | App (`desktop/ui/index.html`) |
|---|---|---|
| Background | `#170a2b` violet | `#0b0d10` near-black |
| Accent | `#52ffa5` / `#6bfdff` mint-cyan | `#6ea8fe` blue |
| Type | General Sans + Mulish | `ui-sans-serif` / Segoe UI |
| Corners | zero-radius, hard edges | 16px cards, 999px pills |

Worse than the visuals: the site sells *"A crew, not a chatbot,"* **26
specialists**, and **"$0.05 — a turn, itemised."** None of that is visible
anywhere in the app. Somebody who buys off that page opens NameOS and cannot find
the thing they bought. **That is a positioning fault wearing a design costume.**

**3. Twenty-one letter-avatars where everyone shows real logos.**
Atlassian is a blue "A", GitHub a white "G". Raycast's extension grid, Jan's model
row and Zoey's integration grid all use real marks. Letters read as placeholder,
and placeholder reads as *not actually integrated*. This was my deliberate choice
— hand-drawn brand marks look wrong at every size — and on reflection it was the
wrong call.

**4. Twenty identical blue Connect buttons, no hierarchy, and the grid breaks.**
Every row carries the same saturated primary button, so nothing is recommended
and the panel reads as a chore list. Zapier's second line ("free plan: 50
actions/mo") makes one cell taller and knocks its row out of alignment. The
`CONNECTED` section — the most trust-buying content in the app — is clipped at the
bottom of the dialog.

**5. Eighty-five per cent of the window carries no information.**
The ring fills the frame; the product is a ~440px card in the corner, and the card
crops the ring. Warp gives the whole surface to tasks with model, cost and
duration. LM Studio's hero is the document being built. Ours is a particle ring
that has been the house style of every AI product since 2023 and says nothing
about state.

**6. Labels and verbs contradict themselves across screens.**
The rail item is "Voice" in one shot and "Read aloud" in another — the same
button. In the Skills panel, two rows of identical type carry different verbs
(Edit/Remove vs Show/Remove), and all four starter cards are subtitled the same
four words, *"Edit before saving"*, where the description of what the skill does
should be. Rail register is mixed: New / Folder / Connect / Skills / About you /
Voice / Permission / Tour — actions, nouns and a sentence fragment.

**7. No examples anywhere.** No starter prompts, no "try this."

**8. The primary action is styled as the least important thing.** "Write a new
skill" is a grey secondary button in the corner of a panel that exists to do
exactly that.

**9. No keyboard language.** Raycast's whole product is shortcut hints. Our modals
do not even hint Esc.

**10. The marketing site shows no screenshot of the product.** Raycast, Jan, LM
Studio and Warp all lead with real app UI.

### The three that move the needle for the least work

1. **Make the good empty state the default first frame**, add three clickable
   example prompts, and demote the mic error to a quiet inline chip with an
   "Open settings" button. One screen, one file.
2. **Real vendor logos**, and cut the default Connections view to six recommended
   with the rest behind "All."
3. **Pick one accent.** One CSS variable in each file. It ends the "two products"
   read at a glance.

### What we do better, honestly

**Connection honesty, and it is genuinely best in class.** Grey means nothing set
up, amber means a key exists but has never passed a real test, green is earned by
an actual round trip. Every competitor checked shows binary connected/not.
`Claude Code — BUILT IN — Connected — 2.1.246` with a Re-check button naming the
real version is more honest than any page read. Rail labels under icons beat
Raycast's and Zoey's hover-only discovery.

**Visually: nothing.** The ring is competent and generic. Our advantage is
behavioural honesty and it is completely invisible on the marketing site — which
is the real waste.

### What could not be checked

- **ZoeyOS's actual app** — no public screenshots, gated download.
- **ChatGPT desktop** and **Perplexity desktop** — both returned 403.
- **Claude Desktop** — no page with verified UI shots opened.
- **Msty Studio's app UI** — homepage shows device composites, not interfaces.
- Everything above is from **screenshots and source, not a running app.** Motion,
  transition timing and focus behaviour are unassessed.

Sources: zoeyos.com, raycast.com, warp.dev, lmstudio.ai, jan.ai, msty.ai,
openwebui.com

---

## Screenshots this was read from

`desktop/shots/` — `ux-main.png`, `grid-all.png`, `skills-list.png`, `rows.png`,
`voicebar.png`, `training-panel2.png`.
