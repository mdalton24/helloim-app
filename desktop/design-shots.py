#!/usr/bin/env python3
"""Capture the NameOS app for a design review — every main surface, three widths.

WHY THIS IS SEPARATE FROM render-check.py. That file ASSERTS: it proves the ring
renders, the folder shows a name, the update chip is hidden. This one PROVES
NOTHING and is not meant to. It exists so somebody can LOOK, and the fault it
was built for is the one no assertion catches: a screen that works perfectly and
looks wrong.

ONE BROWSER, DRIVEN SERIALLY, FROM ONE PLACE. Nine headless Chromiums running at
once took this machine down for seventy minutes on 2026-08-23 — the driver ran
out of GPU contexts, which no memory check would have seen, and the desktop
froze with the box underneath never panicking. So the reviewers never launch a
browser; they are handed these files.

THE THREE WIDTHS ARE THE POINT.
  1180x800  the window the app actually opens at (tauri.conf.json)
   720x520  the MINIMUM the window can be dragged to (minWidth/minHeight)
  1600x1000 maximised on a normal laptop

720x520 is the one nobody looks at and the one that breaks. A hero on
markdalton.com was signed off as "tight but not broken" and was overlapping at
Mark's own width, because it was only ever seen at the width it was designed at.

  python3 design-shots.py            -> shots/design/*.png
"""
import base64
import http.server
import json
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "shots" / "design"
UI = HERE / "ui"

# label -> (width, height). The names end up in the filenames the reviewers read.
SIZES = [("window", 1180, 800), ("min", 720, 520), ("max", 1600, 1000)]

# --hero captures ONE frame for the marketing site instead of the review grid.
#
# It is a different job from the review shots and that is why it is a flag
# rather than just picking 01-main out of the grid. A review shot should show
# the product cold and empty, because an empty state is the thing worth
# reviewing. A hero shot has about one second to say what the product does.
#
# Iris, 2026-08-27, judging the first attempt: "a real sentence in the composer
# and a folder name that is a name... under a headline reading 'Give it a name'
# that detail did more work than the headline."
#
# NEITHER OF THESE INVENTS A CAPABILITY, which is the line that matters. The
# sentence is typed, not answered -- no fabricated reply, no fake result. The
# folder is just a folder with a name, which is what everyone's actually is.
HERO = "--hero" in sys.argv

# --only=SUBSTR narrows the grid to the views whose label contains SUBSTR.
# ONE BROWSER IS THE RULE (see the header), so the whole grid is 45 serial
# captures and iterating on one surface should not cost all of them. It filters
# the LABELS only -- every width still runs, because the width nobody looks at
# is the width that breaks.
ONLY = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), "")
REVIEW_WORKDIR = "C:\\\\Users\\\\mdalt\\\\Documents\\\\NameOS"
HERO_WORKDIR = "C:\\\\Users\\\\mdalt\\\\Documents\\\\Atlas"
HERO_SENTENCE = "Summarise what changed in this folder this week"

# label -> JS that puts the app on that surface. Each runs from a clean state:
# every sheet is closed first, so a view cannot inherit the previous one.
VIEWS = [
    ("01-main", ""),
    ("02-connections", "document.getElementById('connBtn').click()"),
    # THE APPS SHEET AS A FRESH INSTALL MEETS IT -- nothing connected, so the
    # two brain sections show "Set up" and "Connect" rather than "Disconnect".
    #
    # WHY IT IS A VIEW OF ITS OWN. The seed above has both brains connected,
    # which is a real state and the WRONG one to review a first-run screen in:
    # the buttons are a different component (.svcConnect, outlined and wider,
    # against .svcActive's plain text), so the row it produces is a different
    # row. Every design shot of this sheet ever taken had a signed-in Claude in
    # it. Nobody had looked at the screen the person actually arrives on.
    ("02b-connections-cold",
     "document.getElementById('connBtn').click();"
     "setTimeout(()=>{ claudeState = { ready:false, version:'' }; providers = [];"
     "  if (window.renderRecommendedAi) renderRecommendedAi();"
     "  else renderRecommendedAi(); }, 500)"),
    ("03-connection-form",
     "document.getElementById('connBtn').click();"
     "setTimeout(()=>{const b=document.getElementById('addApi'); if(b) b.click();}, 400)"),
    # THE SIGN-IN SHEET, which is where "Set up" on the Claude row lands and is
    # therefore the second screen of a fresh install. Its three rows are
    # .connRow with NO status dot -- a name/why block and a button cluster --
    # so it is the surface most exposed to any change to how that row aligns,
    # and it had no capture of its own until 2026-08-28.
    ("03b-signin",
     "(() => { const s = document.getElementById('signinSheet');"
     " if (s) s.hidden = false; try { paintSigninSheet(); } catch (e) {} })()"),
    ("04-skills", "document.getElementById('skillBtn').click()"),
    # THE TAB MUST BE CLICKED, NOT ASSUMED. The Profile sheet remembers which
    # tab was last open, and 06-about-me runs right after this one -- so at the
    # SECOND and THIRD window sizes, "05-about-you" was photographing About me.
    # Vance caught it 2026-08-27 by noticing the tab underline disagreed with
    # the filename, which means the About-you screen at 720x520 had never
    # actually been looked at by anyone. A shot whose NAME lies is worse than a
    # missing one: it gets reviewed, passed, and the real screen never is.
    ("05-about-you",
     "document.getElementById('aboutBtn').click();"
     "setTimeout(()=>{const t=document.getElementById('tabYou'); if(t) t.click();}, 400)"),
    ("06-about-me",
     "document.getElementById('aboutBtn').click();"
     "setTimeout(()=>{const t=document.getElementById('tabMe'); if(t) t.click();}, 400)"),
    ("07-updates", "document.getElementById('markBtn').click()"),
    # THE MEMORY HUB, and it is photographed POPULATED because an empty one
    # cannot show the thing the panel exists for -- telling apart what the
    # person wrote from what the assistant wrote.
    ("08-memory",
     "document.getElementById('aboutBtn').click();"
     "setTimeout(()=>{const t=document.getElementById('tabMemory'); if(t) t.click();}, 400)"),
    # THE BRAIN PICKER. Mark: "we need to let them pick and connect their ai
    # components." Photographed with all four states present for the same
    # reason as the connectors -- an all-green screen hides the design problem.
    ("09-brain",
     "(document.getElementById('brainChip')||document.getElementById('connChip')"
     "||{click(){}}).click();"
     "setTimeout(()=>{ if (window.openBrainSheet) window.openBrainSheet(); }, 350)"),
    # THE ADD FORM, which is new markup nobody has seen rendered. The kind
    # select is the part that matters: it is where a person chooses whether
    # their endpoint speaks Anthropic's shape or OpenAI's.
    ("10-brain-form",
     "(window.openBrainSheet ? window.openBrainSheet() : 0);"
     "setTimeout(()=>{ const b=[...document.querySelectorAll('button')]"
     ".find(x=>/add another brain/i.test(x.textContent||'')); if(b) b.click(); }, 500)"),
    # THE OTHER THREE COMPONENT TABS. Mark widened the ask from the brain to
    # "their ai components", so these panes are the answer -- and two of them
    # deliberately have no picker yet, which is the thing worth photographing:
    # an explanatory state that says what the component does TODAY beats a
    # blank panel or a control that cannot work.
    ("11-voice",
     "(window.openBrainSheet ? window.openBrainSheet() : 0);"
     "if (window.showBrainPane) window.showBrainPane('voice')"),
    ("12-hearing",
     "(window.openBrainSheet ? window.openBrainSheet() : 0);"
     "if (window.showBrainPane) window.showBrainPane('hearing')"),
    ("14-tab-focus",
     "(window.openBrainSheet ? window.openBrainSheet() : 0);"
     "setTimeout(()=>{const t=document.getElementById('tabVoice'); if(t) t.focus();}, 300)"),
    ("13-embeddings",
     "(window.openBrainSheet ? window.openBrainSheet() : 0);"
     "if (window.showBrainPane) window.showBrainPane('embeddings')"),
]

# CLOSING A SHEET IS NOT THE SAME AS RESETTING THE APP -- learned 2026-08-28.
# 02b-connections-cold reaches in and sets `claudeState` and `providers` to
# their fresh-install values so the brain rows can be photographed cold. Those
# are module globals: nothing puts them back, so every view captured AFTER it
# was rendered against a Claude that was not installed, and the only tell was a
# topbar chip reading "Claude not working" in a shot nobody was looking at the
# topbar in. A review grid whose later frames inherit an earlier frame's state
# is the 05-about-you fault again -- a shot whose name lies gets reviewed,
# passed, and the real screen never is.
# So the reset is part of closing, re-read from the stub rather than restored
# from a saved copy: whatever the seed says today is what every view starts
# from. The 0.4s the caller already sleeps is far more than a stub that
# resolves on the microtask queue needs.
CLOSE_ALL = """(() => {
  for (const id of ['connSheetClose','aboutClose','updateClose','skillSheetClose']) {
    const b = document.getElementById(id);
    if (b && b.click) { try { b.click(); } catch (e) {} }
  }
  for (const s of document.querySelectorAll('.sheet')) s.hidden = true;
  (async () => {
    try {
      const iv = window.__TAURI__.core.invoke;
      claudeState = await iv('preflight');
      const r = await iv('list_providers');
      providers = Array.isArray(r && r.providers) ? r.providers : [];
      if (window.paintIndicator) paintIndicator();
    } catch (e) {}
  })();
  return true;
})()"""


def free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def serve(port):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(UI), **k)

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


class CDP:
    def __init__(self, port):
        self.port = port
        self.n = 0
        self.ws = None

    def connect(self):
        import websocket
        for _ in range(60):
            try:
                tabs = json.loads(urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json").read())
                pages = [t for t in tabs if t["type"] == "page"]
                if pages:
                    self.ws = websocket.create_connection(
                        pages[0]["webSocketDebuggerUrl"], timeout=40)
                    return
            except Exception:
                time.sleep(0.5)
        raise SystemExit("could not attach to Chromium over CDP")

    def send(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise SystemExit(f"{method}: {m['error']}")
                return m.get("result", {})

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr,
                      awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    port, dport = free_port(), free_port()
    serve(port)

    proc = subprocess.Popen(
        ["/snap/bin/chromium", "--headless=new", f"--remote-debugging-port={dport}",
         "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         "--remote-allow-origins=*", "--window-size=1180,800",
         f"http://127.0.0.1:{port}/index.html"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    written = []
    try:
        cdp = CDP(dport)
        cdp.connect()
        cdp.send("Runtime.enable")
        cdp.send("Page.enable")

        # A plain browser is not Tauri, so every invoke() throws and the app
        # renders as if nothing works. The stub is what makes these surfaces
        # photographable at all. It returns MIXED state on purpose -- one
        # connector proven, one never tested, one failed -- because a screen
        # where everything is green photographs beautifully and hides the exact
        # design problem worth reviewing.
        cdp.send("Page.addScriptToEvaluateOnNewDocument", source=r"""
          window.__TAURI__ = { core: { invoke: async (cmd) => {
            if (cmd === 'default_workdir') return '__WORKDIR__';
            if (cmd === 'is_folder') return true;
            if (cmd === 'preflight') return { ready: true, version: '2.1.246' };
            if (cmd === 'scan_notes') return { nodes: [], edges: [], truncated: false };
            if (cmd === 'load_profile') return { about:'', goal:'', memory:'',
              assistantName:'Jarvis', personality:'', wakeWord:'' };
            if (cmd === 'check_update') return { available:false, currentVersion:'0.1.0' };
            if (cmd === 'is_running') return false;
            if (cmd === 'list_skills') return [];
            /* THE MEMORY HUB, SEEDED THE SAME WAY THE CONNECTORS ARE — mixed
               on purpose. An empty Hub photographs beautifully and hides the
               entire reason the panel exists, which is telling apart what the
               PERSON wrote from what the ASSISTANT wrote, and un-poisoning the
               second kind. So: some of each, one already confirmed by a human,
               and one long enough to test how a row wraps. */
            if (cmd === 'list_facts') return [
              { id:1, kind:'preference', text:'Prefers replies kept short.',
                scope:'', source:'the assistant', at:Math.floor(Date.now()/1000)-600, verified:false },
              { id:2, kind:'preference', text:'No emoji in anything client-facing.',
                scope:'', source:'', at:Math.floor(Date.now()/1000)-90000, verified:true },
              { id:3, kind:'project', text:'The Riverside quote goes out before the end of the month.',
                scope:'', source:'the assistant', at:Math.floor(Date.now()/1000)-4000, verified:false },
              { id:4, kind:'decision', text:'We invoice on completion, not on deposit.',
                scope:'', source:'', at:Math.floor(Date.now()/1000)-200000, verified:true },
              { id:5, kind:'fact', text:'The Stripe key is kept in 1Password, not on this machine, and only Dana has it.',
                scope:'', source:'the assistant', at:Math.floor(Date.now()/1000)-30000, verified:false },
            ];
            if (cmd === 'memory_stats') return { total:5, assistantCount:3, verifiedCount:2 };
            /* THE TWO BRAIN SECTIONS AT THE TOP OF THE APPS SHEET, WHICH THIS
               CAPTURE COULD NOT PHOTOGRAPH AT ALL UNTIL 2026-08-28. There was
               no stub for `recommended_ai`, so it resolved to null and
               renderRecommendedAi() threw on `RECO_AI.cloud` -- the two
               sections simply never painted, in every design shot ever taken
               of this sheet. A capture tool that silently omits a region is
               worse than one that fails: the region gets reviewed by nobody
               and everybody believes it was looked at.
               COPIED FROM THE RUST, NOT INVENTED -- CLOUD_AI and LOCAL_AI in
               brain_setup.rs, letter, colour, note and port included. A seed
               that drifts from the shipped constants photographs a product
               nobody ships. */
            if (cmd === 'recommended_ai') return {
              cloud: [ { id:'claude', name:'Claude', letter:'C', colour:'#d97757',
                kind:'claude', base_url:'',
                note:'The brain NameOS ships with. Install it and sign in — no key to find.',
                download_url:'' } ],
              local: [ { id:'ollama', name:'Ollama', letter:'O', colour:'#6fd08c',
                kind:'local', base_url:'http://127.0.0.1:11434',
                note:'The one NameOS knows best — it measures your machine and only offers models that fit.',
                download_url:'https://ollama.com/download' } ],
            };
            /* THE BRAIN PICKER, seeded across every honesty state the product
               still HAS: green and in use, proven and idle, a key that has
               never answered, one that was tested and failed, and one retired
               kind. A screen where everything is green photographs beautifully
               and hides the design problem worth reviewing.

               RE-SEEDED 2026-08-28 AGAINST THE SHIPPED BACKEND, and the drift
               it had was not cosmetic. Three rows were `openai-compatible`,
               a kind `ROUTABLE_KINDS` no longer contains, so this capture was
               photographing a picker offering four cloud brains that the app
               removes on load. And the Claude row carried the caveat
               "Anthropic sees the conversation", which `caveat_for("claude")`
               has never returned -- a test asserts it is empty. So the shot
               showed the honest sentence in a place the product does not say
               it, which is the one direction a seed must never drift.

               THE RETIRED ROW'S NOTE IS RETIRED_NOTE FROM providers.rs, WORD
               FOR WORD, and its length is the point: it is what a person who
               had a cloud brain yesterday actually sees today, and it is the
               row the status dot was floating in the middle of. */
            if (cmd === 'list_providers') return { active: 'p-local', providers: [
              { id:'claude', kind:'claude', name:'Claude', builtin:true, model:'',
                baseUrl:'', connected:true, checkedAt:String(Math.floor(Date.now()/1000)-60),
                lastError:'', hasSecret:false, disconnected:false, caveat:'' },
              { id:'p-local', kind:'local', name:'Hermes 3 70B Instruct, quantized', builtin:false,
                model:'hermes3:8b', baseUrl:'http://127.0.0.1:11434',
                connected:true, checkedAt:String(Math.floor(Date.now()/1000)-900),
                lastError:'', hasSecret:false, disconnected:false,
                caveat:"Runs on your own machine. Free and private. Slower than Claude, and smaller models get details confidently wrong — good for drafts and summaries, not for work you'd act on unchecked." },
              { id:'p-fresh', kind:'local', name:'Qwen 3 30B', builtin:false,
                model:'qwen3-coder:30b', baseUrl:'http://127.0.0.1:11434',
                connected:false, checkedAt:'', lastError:'', hasSecret:false, disconnected:false,
                caveat:"Runs on your own machine. Free and private. Slower than Claude, and smaller models get details confidently wrong — good for drafts and summaries, not for work you'd act on unchecked." },
              { id:'p-bad', kind:'local', name:'Workshop endpoint',
                builtin:false, model:'llama-3.3-70b', baseUrl:'http://192.168.1.9:11434',
                connected:false, checkedAt:String(Math.floor(Date.now()/1000)-300),
                lastError:'Nothing answered at that address.', hasSecret:false, disconnected:false,
                caveat:"Runs on your own machine. Free and private. Slower than Claude, and smaller models get details confidently wrong — good for drafts and summaries, not for work you'd act on unchecked." },
              { id:'c-retired', kind:'openai-compatible', name:'OpenAI', builtin:false,
                model:'', baseUrl:'https://api.openai.com/v1',
                connected:false, checkedAt:'', lastError:'', hasSecret:true, disconnected:false,
                migrationNote:'This brain connected to an AI company NameOS no longer offers. Nothing was sent anywhere, and the key you saved is still stored safely on this computer. Claude and a brain on your own machine are the two choices now — pick one above, or remove this row.',
                caveat:'' },
            ] };
            if (cmd === 'detect_local_brain') return { running:true, apiOk:true,
              version:'0.33.1', models:['hermes3:8b','qwen3-coder:30b','gpt-oss:20b'],
              problem:null };
            if (cmd === 'list_plugins') return [];
            if (cmd === 'list_connectors') return [
              { id:'a', kind:'api', name:'OpenAI', provider:'openai', baseUrl:'', model:'gpt-5',
                args:[], connected:true, checkedAt:String(Math.floor(Date.now()/1000)-120),
                lastError:'', hasSecret:true },
              { id:'b', kind:'api', name:'Anthropic', provider:'anthropic', baseUrl:'', model:'',
                args:[], connected:false, checkedAt:'', lastError:'', hasSecret:false },
              /* THE TRUE AMBER ROW, and it was missing until 2026-08-27.
                 The app has FOUR states and this capture only ever showed
                 three: green, grey and red. Amber -- a key IS stored and it
                 has never answered -- had no row, so the one state that is
                 hardest to explain and most central to the honesty claim was
                 the one nobody could photograph. Iris needed it for the
                 connections page, whose whole animation holds on this beat.
                 hasSecret true, connected false, no error: that is exactly
                 "something is stored and it has never answered a real
                 request", which is what nameos.ai says amber means. */
              { id:'d', kind:'api', name:'Groq', provider:'openai',
                baseUrl:'https://api.groq.com/openai/v1', model:'llama-3.3-70b',
                args:[], connected:false, checkedAt:'', lastError:'', hasSecret:true },
              { id:'c', kind:'mcp', name:'Filesystem', provider:'', command:'npx',
                args:['-y','@modelcontextprotocol/server-filesystem','.'],
                connected:false, checkedAt:String(Math.floor(Date.now()/1000)-9000),
                lastError:'The server started but did not answer in time.', hasSecret:false },
              { id:'e', kind:'api', name:'Old workshop key', provider:'mystery',
                baseUrl:'https://example.invalid', model:'', args:[],
                connected:false, checkedAt:'', hasSecret:true,
                lastError:"API providers now live in the Brain menu. This one's shape isn't recognised, so it stays here and its key is still stored. Add it under Brain yourself, or remove this row." },
            ];
            return null;
          } }, event: { listen: () => {} } };

          /* THE MICROPHONE IS THE ONE STUB THAT IS ABOUT HONESTY, NOT
             CONVENIENCE. Headless Chromium has no microphone, so
             SpeechRecognition.start() fires onerror and the app correctly
             paints "Microphone is blocked, so it cannot hear you." -- across
             the top of the window, in the largest type on the screen.

             That is the app behaving properly and the CAPTURE lying. Iris
             caught it about to ship as the hero of the marketing site on
             2026-08-27: leading a product page with an error the product does
             not have is the same lie as leading with a capability it does not
             have, pointed the other way.

             So the stub reports what a real machine with a working microphone
             reports -- idle and available. It never fabricates a TRANSCRIPT;
             it just does not invent a failure. Any real fault in the voice
             path still surfaces, because nothing here touches onresult. */
          const QuietRecognition = function () {
            this.continuous = false; this.interimResults = false; this.lang = 'en-US';
            this.onresult = null; this.onerror = null; this.onend = null;
            this.onstart = null; this.onaudiostart = null;
            /* IN HERO MODE THIS DELIBERATELY DOES NOT FIRE onstart, AND THAT
               IS A HONESTY FIX RATHER THAN A COSMETIC ONE.

               onstart puts the mic button into #mic.listening -- red border,
               red icon, red fill, and a pulse animation. In the review grid
               that is correct: the app really does listen for the wake word
               while idle, and that is worth photographing.

               In the hero it is a lie twice over. Iris, 2026-08-27: the frame
               showed a complete typed sentence with Send lit AND the mic
               recording, and "you do not type a full sentence while it is
               recording you" -- the product cannot be in both states at once.
               Worse, a screenshot freezes the pulse, so the red loses its
               "recording" reading and defaults to the only other thing red
               means on a dark page, which is an error. It was the one warm
               hue on the whole marketing page, inside the dominant element.

               So the hero photographs someone typing, with the mic idle,
               which is a state the app genuinely has. */
            this.start = function () {
              if (__HERO__) return;
              if (this.onstart) try { this.onstart({}); } catch (e) {}
            };
            this.stop = function () {};
            this.abort = function () {};
            this.addEventListener = function () {};
            this.removeEventListener = function () {};
          };
          window.SpeechRecognition = QuietRecognition;
          window.webkitSpeechRecognition = QuietRecognition;
        """.replace("__WORKDIR__", HERO_WORKDIR if HERO else REVIEW_WORKDIR)
           .replace("__HERO__", "true" if HERO else "false"))

        # And grant the permission itself, so anything asking the Permissions
        # API gets the same answer the stub above implies. Belt and braces --
        # these are two different code paths and only one of them is stubbed.
        try:
            cdp.send("Browser.grantPermissions", permissions=["audioCapture"])
        except Exception:
            pass  # Older CDP builds refuse it; the stub above is the real fix.
        cdp.send("Page.reload")
        time.sleep(3.5)

        # Past the sign-in overlay -- exactly what signIn() does.
        cdp.js("""(() => {
          const g = document.getElementById('authGate');
          const a = document.getElementById('app');
          if (g) g.hidden = true;
          if (a) a.hidden = false;
          return !!(g && a);
        })()""")
        time.sleep(2.0)

        if HERO:
            # The app's own default window from tauri.conf.json -- so the site
            # shows what a customer actually gets, not a flattering variant.
            cdp.send("Emulation.setDeviceMetricsOverride", width=1180, height=800,
                     deviceScaleFactor=2, mobile=False)
            time.sleep(1.2)
            cdp.js(CLOSE_ALL)
            time.sleep(0.5)
            # Type it the way a person would, so every listener the app has
            # bound to the composer runs and the Send button enables itself.
            # Setting .value alone would leave the button looking disabled,
            # which photographs as a product that does not work.
            typed = cdp.js("""(() => {
              const p = document.getElementById('prompt');
              if (!p) return 'no composer';
              p.value = %s;
              p.dispatchEvent(new Event('input', { bubbles: true }));
              p.blur();
              return p.value;
            })()""" % json.dumps(HERO_SENTENCE))
            if typed != HERO_SENTENCE:
                print(f"  !! composer did not take the sentence: {typed!r}")
            time.sleep(1.5)
            png = cdp.send("Page.captureScreenshot", format="png")["data"]
            p = OUT / "hero-app.png"
            p.write_bytes(base64.b64decode(png))
            written.append(p.name)
            print(f"  {p.name}  (hero, 1180x800 @2x)")
            print(f"\n{len(written)} shot -> {OUT}")
            return 0

        for label, w, h in SIZES:
            # deviceScaleFactor 2 so type and spacing are judgeable rather than
            # guessed at from a blurry 1x capture.
            cdp.send("Emulation.setDeviceMetricsOverride", width=w, height=h,
                     deviceScaleFactor=2, mobile=False)
            time.sleep(1.0)
            for view, opener in VIEWS:
                if ONLY and ONLY not in view:
                    continue
                cdp.js(CLOSE_ALL)
                time.sleep(0.4)
                if opener:
                    cdp.js(f"(() => {{ {opener}; return true; }})()")
                time.sleep(1.3)
                png = cdp.send("Page.captureScreenshot", format="png")["data"]
                p = OUT / f"{view}--{label}-{w}x{h}.png"
                p.write_bytes(base64.b64decode(png))
                written.append(p.name)
                print(f"  {p.name}")
            cdp.js(CLOSE_ALL)
    finally:
        proc.terminate()

    print(f"\n{len(written)} shots -> {OUT}")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
