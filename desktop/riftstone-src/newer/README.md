# Rift Stone — source

This bundle is the complete source for the **Rift Stone** scene: a single self-contained
`rift-stone.html` file plus every asset it needs (in `assets/`).

## Drop it into your AI

Hand this whole folder to your AI coding assistant — Claude, Cursor, Copilot, v0, whatever you
use — and ask it to reimplement it inside the project you already have, whether that's
**React, Next.js, Vue, Svelte, or a plain HTML/JS site**. Because everything lives in one file
with the tunable values grouped up top, the assistant can lift the markup, styles, shaders and
render loop and wrap them in a component that fits your stack.

## Run it as-is first

It loads its assets with relative paths, so serve it from a local web server rather than
double-clicking it:

```sh
npx serve .          # then open the printed URL and click rift-stone.html
# or:  python3 -m http.server
```
