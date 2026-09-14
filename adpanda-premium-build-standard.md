# ADPanda premium build standard — the seven-stage creative direction

**Mark's instruction, 2026-08-23:** *"for the templates that were not working or
referenced in the examples, follow the following prompt"* — and then the seven
stages below, verbatim.

## What this replaces, and why it exists

The nine per-industry sites were built with a TemplateMonster demo as a
structural framework. **For four of them there was no usable framework at all**,
and nobody knew that until the sites were audited on 2026-08-23:

| site | what the reference actually was |
| --- | --- |
| Ironpeak Exteriors | RoofOnFire — **502 Bad Gateway**, host down |
| Copper Skillet | Quick Food — **403 Forbidden**, host refuses |
| Forge Athletic | Hazel — the theme's **"25 prebuilt websites" showcase page**, not a design |
| Marin & Co Realty | an **OpenCart e-commerce store** template — cart, "0 items", PayPal logos |

Those four were built from a theme *name* and a guess. **This document is what
they get instead of a template.** It is a creative direction, not a framework —
which is the right substitute, because the problem was never "no template", it
was "no direction".

**AND THE REASON NOBODY SAW THE TEMPLATES IS BANKED SEPARATELY AND MATTERS MORE
THAN THIS FILE:** the demo hosts refuse headless browsers by user agent, and the
URL Mark sends is only a wrapper around an `iframe`. Both are solved; see the
capture method in `IN-FLIGHT.md`. **A future build must not re-derive that.**

## The seven stages — Mark's text, unedited

Run them in order. `[BRAND]` / `[WEBSITE]` is the site being built.

**1. Create the High-End Creative Direction.** Act as an award-winning digital
creative director. Transform [BRAND] into an ultra-smooth, premium website that
feels crafted by a world-class digital studio. Define the visual identity, mood,
typography, color palette, layout system, imagery, signature interactions, and
motion language. Make every detail feel distinctive, modern, and intentional —
while keeping the experience conversion-focused, memorable, and completely
original.

**2. Design the Complete Experience.** Act as a world-class UX/UI designer.
Design the complete website experience for [BRAND]. Map out the navigation, hero
section, content flow, storytelling, product/service presentation, social proof,
CTAs, forms, footer, and mobile experience. For every section, define its
purpose, visual hierarchy, composition, interactions, and transition to the next.
Make the entire journey feel seamless, premium, intuitive, and effortless to
navigate.

**3. Create the Signature Hero.** Act as an elite creative technologist. Design a
signature hero section for [BRAND] built around one unforgettable visual concept.
Define the composition, typography, imagery or 3D elements, lighting, depth,
entrance animation, hover states, cursor interactions, and first-scroll
transition. Make the hero instantly captivating while clearly communicating the
brand's core value within seconds.

**4. Engineer Ultra-Smooth Motion.** Act as a world-class web motion designer.
Create a premium motion system for [WEBSITE]. Define the page-load choreography,
scroll reveals, easing, parallax, text animations, image transitions, hover
states, cursor effects, page transitions, and micro-interactions. Make every
movement feel fluid, intentional, and beautifully connected. Prioritize
performance, consistency, and storytelling — never unnecessary visual effects.

**5. Build It.** Act as a senior AI web engineer. Create a step-by-step sequence
to build [WEBSITE] without writing code manually. Cover the architecture,
components, responsive design, styling, animations, interactions, smooth
scrolling, forms, SEO, accessibility, and performance. Build the site in stages.
**Inspect the existing work before making changes, test every update, fix errors,
and preserve all working features throughout development.**

**6. Make It Feel Agency-Built.** Act as a premium digital-agency creative
director. Audit [WEBSITE/SCREENSHOTS] and identify everything that makes it feel
generic, cheap, or obviously AI-generated. Improve the typography, spacing,
composition, hierarchy, imagery, motion, transitions, interactions, responsive
behavior, and micro-details. Provide specific, actionable changes that add
polish, sophistication, and the unmistakable feel of a custom-built website from
a world-class studio.

**7. Final Smoothness & Launch Audit.** Act as my senior web engineer and
creative QA director. Perform a final audit of [WEBSITE] covering animation
smoothness, responsiveness, performance, accessibility, navigation, forms, SEO,
browser compatibility, visual consistency, and conversion. Rank every issue by
impact and priority, then provide exact fixes. Finish with a concise launch
checklist to ensure the website is fast, flawless, ultra-polished, and fully
production-ready.

## The house rules the seven stages do NOT repeal

Stage 5 says "preserve all working features". On these sites that is specific,
and losing any of it is a regression no amount of polish makes up for:

- **The lead form posts to `/api/lead`** with `{name,email,phone,industry,note,website}`,
  a real success AND error state, a visually-hidden honeypot `name="website"`
  (tabindex -1), and an empty `<div id="tsWidget"></div>` where the captcha goes.
  **No SMS or texting language anywhere.**
- **The honesty footer, exact.** Real-prospect concept sites (713 Boxing, Latinos
  Hair & Nail): `A concept by ADPanda for <Business>. Not their official site.`
  Every fictional demo: `An ADPanda sample site.`
- **One self-contained `index.html`.** Inline CSS and JS, no build step. Fonts via
  Google Fonts `<link>` or a system stack — **never our `/fonts/` files**, so the
  page renders standalone under `file://`.
- **Royalty-free imagery only** (Unsplash). **Never hotlink templatemonster.com or
  template-help.com assets**, and never imply a theme is ours.
- **No invented statistics.** Plausible placeholder copy for fictional businesses
  is fine; a specific fake number presented as real is not.
- **Accessibility is not a stage-7 afterthought.** Contrast AA, keyboard
  operable, visible focus, and `prefers-reduced-motion` honoured — stage 4's
  motion system must degrade to nothing when that is set.
- **Clean at 1440 AND 390 wide.**

## Rendering — the rule that cost us the machine

**DO NOT FAN OUT AGENTS THAT EACH OPEN A BROWSER.** On 2026-08-23 nine builders
each spawned headless chromium to check their own work; ~36 launches in fifteen
minutes exhausted the GPU's *contexts* (not its memory), the card's firmware
stopped answering, and Mark had to hold the power button.

**Rendering is central and serial.** One browser at a time, from the main
session, after the work lands. `hooks/render-gate.py` refuses a launch when the
box is already loaded — treat it as the net, not the rule.

**And a screenshot taken too early lies.** The 713 Boxing hero looked broken and
overlapping in a 20-second capture and was perfect at 40 seconds — it was caught
mid-animation. **Give a page with an entrance animation time to finish before
judging it**, and re-shoot before reporting a fault.
