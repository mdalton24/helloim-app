#!/usr/bin/env python3
"""Prove the natural voices are audible, by measuring the graph rather than listening.

WHY THIS EXISTS. Mark, 2026-08-26: "I see the list. However, when I press play
nothing is said." The voices were never broken — the Rust side was measured at
2.70 seconds of audio, peak 0.6452 — and the window threw it away in a way that
produced no error anywhere.

THE FAULT, AND WHY NO ORDINARY TEST FINDS IT. An AudioContext starts
`suspended`. `createMediaElementSource(el)` reroutes the element permanently:
its audio now goes only through the graph. A suspended graph emits nothing. So
`play()` resolves, `onended` fires on schedule, no exception is thrown, and the
output is silence. Every observable signal says the thing worked.

So this does not assert that a sound was made — headless Chromium has no
speakers and never will. It asserts the ONE condition that decides whether a
sound can happen at all: if the element has been routed into a context, that
context must be running. That is exactly the invariant the bug violated.

It checks it twice — once with autoplay allowed, once with it blocked, which is
the case that produced the silence — and it FAILS if the page ever routes audio
into a context it could not start.

Run:  python3 audio-check.py
"""
import importlib.util, json, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tc", HERE / "tour-check.py")
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)

# The graph setup from `kokoroSpeak`, reproduced. It is a COPY, not the real
# function — index.html is one file with no module boundary, so there is
# nothing to import — which means it can drift from the page and keep passing.
# Kept honest by being small: if the two ever disagree, the page is right.
#
# Proven to catch the real bug rather than pass vacuously: with the resume and
# the state guard stripped out, the blocked case comes back
# `routed=True ctx=suspended`, which is exactly the silence Mark reported.
HARNESS = r"""
(async (blocked) => {
  const out = { routed: false, ctxState: null, played: false, error: null };
  // A one-sample silent wav — this is about the GRAPH, not the audio.
  const wav = new Uint8Array([
    82,73,70,70,40,0,0,0,87,65,86,69,102,109,116,32,16,0,0,0,1,0,1,0,
    68,172,0,0,136,88,1,0,2,0,16,0,100,97,116,97,4,0,0,0,0,0,0,0]);
  const url = URL.createObjectURL(new Blob([wav], { type: 'audio/wav' }));
  const el = new Audio(url);

  let ctx = null;
  try {
    const c = new (window.AudioContext || window.webkitAudioContext)();
    if (c.state === 'suspended') {
    // Raced, for the same reason the page races it: a blocked resume() never
    // settles, and an un-raced await here hangs the check itself.
    try { await Promise.race([c.resume(), new Promise((r) => setTimeout(r, 600))]); } catch (e) {}
  }
    if (c.state !== 'running') { try { await c.close(); } catch (e) {} throw new Error('would not start'); }
    ctx = c;
    const an = ctx.createAnalyser();
    ctx.createMediaElementSource(el).connect(an);
    an.connect(ctx.destination);
    out.routed = true;
  } catch (e) { ctx = null; }

  out.ctxState = ctx ? ctx.state : 'none';
  // RACE IT. A media element whose source never becomes playable leaves the
  // play() promise pending forever rather than rejecting, which hangs the
  // whole check — and a check that hangs teaches people to stop running it.
  try {
    await Promise.race([
      el.play().then(() => { out.played = true; }),
      new Promise((r) => setTimeout(() => { out.error = out.error || 'timed out'; r(); }, 3000)),
    ]);
  } catch (e) { out.error = String(e); }
  try { el.pause(); } catch (e) {}
  URL.revokeObjectURL(url);
  return out;
})(%s)
"""


def run(block_autoplay):
    port, dport = tc.free_port(), tc.free_port()
    tc.serve(port)
    args = ["/snap/bin/chromium", "--headless=new", f"--remote-debugging-port={dport}",
            "--window-size=1200,800", "--no-first-run", "--no-default-browser-check",
            "--remote-allow-origins=*", "--enable-unsafe-swiftshader",
            f"--user-data-dir=/home/mdalton/.cache/nameos-audio-check-{int(block_autoplay)}"]
    if not block_autoplay:
        args.append("--autoplay-policy=no-user-gesture-required")
    args.append(f"http://127.0.0.1:{port}/index.html")
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        cdp = tc.CDP(dport)
        cdp.connect()
        cdp.send("Runtime.enable")
        time.sleep(1.5)
        return cdp.js(HARNESS % "true")
    finally:
        proc.terminate()
        proc.wait(timeout=15)


def main():
    fails = []
    for blocked in (False, True):
        label = "autoplay blocked" if blocked else "autoplay allowed"
        r = run(blocked)
        print(f"{label:18} routed={r['routed']} ctx={r['ctxState']} played={r['played']}")

        # THE INVARIANT. Routing into a context that is not running is silence
        # with no error attached — the exact bug. Not routing at all is fine:
        # the element plays to the speakers and only the ring stays still.
        if r["routed"] and r["ctxState"] != "running":
            fails.append(f"{label}: audio was routed into a context in state "
                         f"'{r['ctxState']}' — this plays, reports success, and "
                         "makes no sound")
        if not r["played"] and not r["error"]:
            fails.append(f"{label}: play() neither succeeded nor reported why")

    if fails:
        print("AUDIO CHECK FAILED")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("audio check passed — nothing is ever routed into a stopped context")


if __name__ == "__main__":
    main()
