# ADPanda per-industry site build — shared rules

Mark: "rebuild the template as a site with our content" + "template are just framework
lets use for those sites" + "just build them all, don't check in." So: use the referenced
TemplateMonster theme as a STRUCTURAL FRAMEWORK only (section order, energy, the kind of
layout that suits this industry) and build an original, on-brand site with OUR content.
Not a pixel clone. Not a link-out.

## The reference template
- You'll be given a live demo URL. Try to capture it ONCE or TWICE with headless snap
  chromium (`/snap/bin/chromium --headless=new --no-sandbox --hide-scrollbars
  --window-size=1440,6000 --virtual-time-budget=12000 --screenshot=$HOME/shots/<slug>-ref.png "<url>"`;
  write under $HOME). The template-help.com hosts are FLAKY (intermittent 502). If it
  doesn't load in two tries, DO NOT keep retrying — it's just a framework. Proceed from
  the theme's name/type + your own judgement + the design skill. A great site matters more
  than matching the demo.

## Build
- ONE self-contained `index.html`, no build step. Inline CSS + JS.
- Use the **design-taste-frontend skill**. Anti-slop: one accent, motion motivated, real
  hierarchy, a11y (contrast AA, keyboard, prefers-reduced-motion). Clean on desktop AND
  mobile (390px).
- **Fonts: Google Fonts via <link> OR a system stack — NOT our /fonts/ files** (so the page
  renders standalone under file://). Each site can have its own type suited to the template.
- **Images: royalty-free only** (e.g. Unsplash `https://images.unsplash.com/...` or
  `https://source.unsplash.com/...`) — tasteful and relevant to the industry, or strong
  CSS/gradients. NEVER hotlink templatemonster.com or template-help.com assets, and never
  imply the theme is ours.
- **Lead form** (every site): fields Name, Email, Phone (optional), plus a message/note.
  Submit via `fetch('/api/lead',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({name,email,phone,industry:'<INDUSTRY>',note,website:hp})})` with a
  real success + error state. Include a hidden honeypot input `name="website"` (visually
  hidden, tabindex -1) and an empty `<div id="tsWidget"></div>` where the captcha will go.
  No SMS/texting language anywhere.
- **Honesty footer**, exact per site:
  - Real-prospect concept sites (713 Boxing, Latinos Hair & Nail): `A concept by ADPanda
    for <Business>. Not their official site.`
  - Fictional demonstration sites (all others): `An ADPanda sample site.`
- No fabricated review counts/awards beyond any real facts given in the dispatch. For
  fictional demo businesses, plausible placeholder copy is fine — just don't invent a
  specific fake statistic and present it as real.

## Output location + verify
- Build at `/home/mdalton/Documents/adpanda-site/samples/<slug>/index.html` (the slug is
  in your dispatch; it ends in `-v2`). Do NOT touch any other file, the root index.html,
  or any other sample dir.
- **Do NOT deploy.** The main session deploys all nine together after they land.
- **DO NOT SPAWN A BROWSER. THIS RULE REVERSED ON 2026-08-23 AND IT COST THE MACHINE.**
  This file used to say "render-verify with headless chromium ... LOOK at them, and fix
  anything broken". Nine builders were dispatched at once, every one of them followed that
  line, and ~36 chromium launches in fifteen minutes exhausted the GPU's contexts — not its
  memory, its *contexts*. The card's firmware stopped answering at 02:35:37, gnome-shell
  held the driver lock, every process that touched the GPU blocked forever, and Mark had to
  hold the power button at 03:46. **The instruction was correct for ONE builder and lethal
  for nine, and nothing in the wording said which one you were.**
- **So: code-check your own work, and hand back unrendered.** Read your HTML, check the
  structure, check the CSS you wrote actually covers 1440 and 390 wide. **The main session
  renders every site, one at a time, after you land** — that is now the only place a
  browser opens.
- If you genuinely believe something can only be settled by looking at it, **say so in your
  report and hand back anyway.** "I could not verify this without a render" is a finding
  and it costs nothing. A browser you launched to be thorough is the thing that took the
  box down.
- `hooks/render-gate.py` now refuses a browser launch when the box is already loaded, so a
  fan-out like that one gets stopped at the third concurrent browser rather than the
  hundred-and-ninetieth process. **Treat the gate as the net, not the rule — the rule is
  the paragraph above.**

## Report back SHORT
The file path, whether you reached the reference (and how many tries), your screenshot
paths, and anything you deviated on. That's it.
