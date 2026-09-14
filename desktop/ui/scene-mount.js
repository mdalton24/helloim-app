// SCENE-MOUNT — the theme-aware successor to aurelia-mount.js. Mounts
// whichever scene the current theme names on #brainCanvas and re-registers
// the SAME window.RiftBrain surface every existing call site already uses:
//   resize()  setThinking(on)  setSpeaking(on)  bump(v)  pulse()  flare(ok)
// plus ONE new optional method, setListening(on) — see its own comment in
// index.html at anchorArm()/anchorTake(). Nothing else about the bridge
// changed; this file is Iris's spec, build order step 4-5:
// ~/Documents/Iris/2026-08-28-nameos-themes.md.
//
// WHY A NEW CANVAS ON EVERY SWITCH, NOT THE SAME ONE. Bella's scene is
// WebGL; Jarvis's is 2D. A canvas that has already returned a WebGL
// rendering context returns null for '2d' on the same element (and vice
// versa) — that is a hard browser rule, not a bug to work around. So a
// theme switch replaces the <canvas id="brainCanvas"> element itself
// rather than reusing it; every existing lookup does document.getElementById
// AT THE MOMENT IT NEEDS THE CANVAS, never holds a stale reference, so this
// is safe.
import * as aurelia from './scenes/aurelia.js';
import * as board from './scenes/board.js';
// THE TEN PORTED FACES — framework-free Canvas 2D, ported from
// ~/helloim-app/renderer/overlay/scenes/*.js onto this app's own scene
// contract (see scenes/lib/faceScene.js's header for the two-hop port
// note). Each exposes the identical mount(canvas) -> { onResize, destroy,
// setThinking, setSpeaking, setListening, bump, pulse, flare } shape as
// aurelia/board above, so they crossfade and drive off the app's real
// audio/tool signal (window.RiftBrain, forwarded below) with no changes
// here beyond adding them to the registry. None of them has a THEMES
// picker entry yet — no name, voice, or CSS colour tokens have been chosen
// for them — so today they are reachable only by calling
// window.NameOSSwitchScene('<name>') directly; wiring a visible picker
// entry per face is a separate design decision (colours, voice, copy) for
// whoever owns that surface next.
import * as bella from './scenes/bella.js';
import * as blitz from './scenes/blitz.js';
import * as capcom from './scenes/capcom.js';
import * as cyclops from './scenes/cyclops.js';
import * as jarvisFace from './scenes/jarvis.js';
import * as koan from './scenes/koan.js';
import * as noir from './scenes/noir.js';
import * as phreak from './scenes/phreak.js';
import * as retrowave from './scenes/retrowave.js';
import * as sizzle from './scenes/sizzle.js';

const SCENES = {
  aurelia, board,
  bella, blitz, capcom, cyclops, koan, noir, phreak, retrowave, sizzle,
  // keyed 'jarvis-face' rather than 'jarvis' — 'jarvis' the THEME id already
  // means the circuit-board scene (SCENES.board); this is the ported HUD
  // ring/emblem face scene from helloim-app's own scenes/jarvis.js, a
  // different visual under a name that would otherwise collide in meaning
  // even though the object keys themselves can't actually clash.
  'jarvis-face': jarvisFace,
};

const brain = document.querySelector('.brain');
let activeHandle = null;
let activeCanvas = document.getElementById('brainCanvas');

// THIS USED TO GUESS -- Wren, 2026-09-05, tracking down "Bella's circle
// doesn't show on Home." `id === 'jarvis' ? 'board' : 'aurelia'` was a
// second, hand-maintained copy of the exact mapping index.html's own THEMES
// array already owns (`scene:` on each entry), and it drifted the moment
// Vega's eight ported faces got picker entries: 'nova' (scene 'bella'),
// 'blitz', 'capcom', 'cyclops', 'koan', 'noir', 'phreak' and 'retrowave' all
// have their OWN scene id, and every one of them would have been mounted as
// 'aurelia' at first paint regardless -- silently wrong for 8 of the 10
// themes the instant one of them was the stored default, and RIGHT by pure
// coincidence for 'bella' and 'jarvis' only, which is exactly why nobody
// caught it: the two themes anyone tests first happen to be the two this
// function still gets right.
//
// READS `THEMES` DIRECTLY, NO SECOND COPY OF THE MAP -- confirmed this is
// actually reachable, not assumed: index.html's own `<script type="module"
// src="./scene-mount.js">` tag sits after the classic `<script>` that
// declares `const THEMES = [...]`, and a module's top-level scope chains up
// through the same global environment a classic script's top-level
// let/const bindings live in -- verified with a throwaway two-file page
// (one classic script declaring a const, one module reading it back) rather
// than assumed from how module scoping is usually described. So this reads
// the one array index.html already maintains; a theme that changes its
// scene there needs no matching edit here, ever again.
function sceneForTheme() {
  const id = document.documentElement.dataset.theme || 'jarvis';
  if (typeof THEMES !== 'undefined') {
    const theme = THEMES.find((t) => t.id === id);
    if (theme) return theme.scene;
  }
  // THEMES not loaded yet (or the id is stale/unknown) -- same fallback
  // shape as before, kept only as a last resort.
  return id === 'jarvis' ? 'board' : 'aurelia';
}

function mountScene(name, canvas) {
  const mod = SCENES[name] || SCENES.aurelia;
  let handle = null;
  try { handle = mod.mount(canvas); }
  catch (e) {
    // THIS USED TO BE catch (e) {} — same audit that found aurelia.js's own
    // silent catch (see that file's comment). This is the OUTER one: if a
    // scene module's mount() throws synchronously — not just aurelia's, any
    // of the eleven — it landed here with no trace either, one level above
    // the per-scene catches most of them already have. Degrading to the dark
    // surface is still correct; doing it mute is not.
    console.error(`[scene-mount] ${name}.mount() threw — falling back to the dark surface:`, e);
  }
  return handle || {
    onResize() {}, destroy() {}, setThinking() {}, setSpeaking() {},
    setListening() {}, bump() {}, pulse() {}, flare() {},
  };
}

activeHandle = mountScene(sceneForTheme(), activeCanvas);

/* IT MOUNTS BEHIND THE SIGN-IN SCREEN, AND THAT USED TO KILL IT SILENTLY —
 * carried over verbatim from aurelia-mount.js. #app is `hidden` until
 * signIn() runs, so at mount time the canvas measures 0x0; a
 * ResizeObserver on the canvas itself is what tells either scene to look
 * again the moment it is actually revealed. Board.js's own resize() re-reads
 * getBoundingClientRect() the same way aurelia's does, so this fix covers
 * both scenes for free. */
let ro = null;
function watchCanvas(canvas) {
  if (!('ResizeObserver' in window)) return;
  let lastW = 0, lastH = 0;
  ro = new ResizeObserver(() => {
    const r = canvas.getBoundingClientRect();
    const w = Math.round(r.width), h = Math.round(r.height);
    if (!w || !h || (w === lastW && h === lastH)) return;
    lastW = w; lastH = h;
    activeHandle && activeHandle.onResize && activeHandle.onResize();
  });
  ro.observe(canvas);
}
watchCanvas(activeCanvas);

const REDUCE_MOTION = window.matchMedia
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* THE CROSSFADE — Iris's spec §2.3: tokens swap instantly (that is CSS,
 * already done by the moment this runs), the hero canvas crossfades over
 * 180ms: old scene opacity -> 0, unmount, mount new, opacity -> 1. Instant
 * under prefers-reduced-motion. Called by applyTheme() in index.html;
 * guarded there with `window.NameOSSwitchScene &&` like every other
 * cross-file call in this app. */
window.NameOSSwitchScene = function (sceneName) {
  const oldCanvas = activeCanvas;
  const oldHandle = activeHandle;
  // Off the id immediately -- for the ~180ms crossfade both canvases are in
  // the DOM at once, and nothing outside this file ever looks the element
  // up by id (everything goes through window.RiftBrain), so this just
  // avoids a transient duplicate id rather than fixing a real lookup bug.
  oldCanvas.removeAttribute('id');

  // Position/size/display all come from the existing ".brain canvas" CSS
  // rule (it targets the tag, not the id) — only the crossfade needs an
  // inline style here.
  const newCanvas = document.createElement('canvas');
  newCanvas.id = 'brainCanvas';
  newCanvas.style.opacity = REDUCE_MOTION ? '1' : '0';
  newCanvas.style.transition = REDUCE_MOTION ? 'none' : 'opacity 180ms ease';
  brain.appendChild(newCanvas);

  const finish = () => {
    const newHandle = mountScene(sceneName, newCanvas);
    activeCanvas = newCanvas;
    activeHandle = newHandle;
    if (ro) ro.disconnect();
    watchCanvas(newCanvas);
    requestAnimationFrame(() => { newCanvas.style.opacity = '1'; });

    const finishSwap = () => {
      oldHandle && oldHandle.destroy && oldHandle.destroy();
      oldCanvas.remove();
    };
    if (REDUCE_MOTION) finishSwap();
    else newCanvas.addEventListener('transitionend', finishSwap, { once: true });
  };

  if (REDUCE_MOTION) { oldCanvas.style.opacity = '0'; finish(); }
  else {
    oldCanvas.style.transition = 'opacity 180ms ease';
    oldCanvas.style.opacity = '0';
    oldCanvas.addEventListener('transitionend', finish, { once: true });
  }
};

// The same bridge shape every existing call site already relies on, plus
// setListening — forwarded to whichever scene is mounted right now.
window.RiftBrain = {
  resize() { activeHandle && activeHandle.onResize && activeHandle.onResize(); },
  setThinking(on) { activeHandle && activeHandle.setThinking && activeHandle.setThinking(on); },
  setSpeaking(on) { activeHandle && activeHandle.setSpeaking && activeHandle.setSpeaking(on); },
  setListening(on) { activeHandle && activeHandle.setListening && activeHandle.setListening(on); },
  bump(v) { activeHandle && activeHandle.bump && activeHandle.bump(v); },
  pulse() { activeHandle && activeHandle.pulse && activeHandle.pulse(); },
  flare(ok) { activeHandle && activeHandle.flare && activeHandle.flare(ok); },
};
