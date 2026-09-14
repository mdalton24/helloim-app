#!/usr/bin/env python3
"""Render NameOS's UI in a real browser and photograph the ring.

WHY THIS EXISTS. The hero is a WebGL scene with a 2.4s intro dolly and a
bloom pass; a source-level check cannot tell "the ring is there" from "the
module 404'd and the window is black", and a naive screenshot fires while the
dolly is still moving, which looks identical to a broken render. So this drives
Chromium over CDP with real waits, and it FAILS LOUDLY rather than handing back
a black PNG that someone might mistake for a result.

It also proves the two interactions Mark asked for by name:
  * POINTER — moves the mouse into the open ground and checks the scene's
    cursor-strength uniform actually rises. aurelia.js raycasts onto a pick
    sphere; if the canvas were covered or pointer-events were off, this stays 0.
  * SPEECH — calls the same window.RiftBrain.bump() the per-word onboundary
    handler calls, and checks state.level rises and then decays.

Run:  python3 render-check.py          (writes shots/*.png, exits non-zero on fail)
"""
import base64, http.server, json, os, re, socket, socketserver, subprocess, sys
import threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UI = HERE / "ui"
SHOTS = HERE / "shots"
INTRO_SETTLE_S = 4.5          # aurelia.js CONFIG.introSeconds is 2.4
VIEWPORT = (1440, 900)


def free_port():
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
    """Minimal CDP client over the websocket-free HTTP+ws bridge."""

    def __init__(self, port):
        self.port = port
        self.ws = None
        self.n = 0

    def connect(self):
        import websocket  # noqa
        for _ in range(80):
            try:
                tabs = json.load(urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json"))
                page = next(t for t in tabs if t["type"] == "page")
                self.ws = websocket.create_connection(
                    page["webSocketDebuggerUrl"], timeout=30)
                return
            except Exception:
                time.sleep(0.25)
        raise SystemExit("could not attach to Chromium over CDP")

    def send(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method,
                                 "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr,
                      returnByValue=True, awaitPromise=True)
        if r.get("exceptionDetails"):
            raise RuntimeError(f"JS threw: {r['exceptionDetails']}")
        return r["result"].get("value")


def lit_fraction(png_path):
    """Fraction of the frame that is meaningfully brighter than the app's own
    dark surface — i.e. how much of the window the glowing ring occupies."""
    from PIL import Image
    im = Image.open(png_path).convert("L").resize((240, 150))
    px = list(im.getdata())  # small image; a list is fine and avoids the deprecation
    return sum(1 for v in px if v > 40) / float(len(px))


def check_css_comments(html):
    """Unbalanced /* */ inside <style> silently destroys the rule that follows.

    It is not a syntax error to a browser -- the parser just keeps reading, so
    the next selector and its whole block vanish with no console message and no
    failing assertion. Cheap to check here, invisible everywhere else.
    """
    import re
    problems = []
    for i, block in enumerate(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)):
        depth, pos = 0, 0
        while pos < len(block):
            o = block.find("/*", pos)
            c = block.find("*/", pos)
            if o == -1 and c == -1:
                break
            if o != -1 and (c == -1 or o < c):
                depth += 1
                pos = o + 2
            else:
                depth -= 1
                if depth < 0:
                    line = block[:c].count("\n") + 1
                    problems.append(f"style block {i}, line {line}: a `*/` with no "
                                    "`/*` open — everything up to the next `{` is "
                                    "being parsed as a selector")
                    depth = 0
                pos = c + 2
        if depth > 0:
            problems.append(f"style block {i}: a `/*` is never closed")
    return problems


def check_profile_save(html):
    """The window's save must not be able to destroy a field it never sent.

    THE BUG THIS GUARDS, twice in one day: 'About me' posts six fields, the
    voice card is a seventh nobody posts, and the backend used to write the
    whole struct -- so pressing Save on a tab you had not typed in deleted a
    card built from eleven personal answers, silently. `fae55d4` was the same
    shape on the name. profile.rs now takes a patch where an omitted field is
    kept, so BOTH halves of this have to stay true, and only one of them lives
    in Rust:

      1. There is exactly ONE save_profile call site. Setup's Finish reaches it
         through the same form submit -- if a second call appears, the two can
         send different field sets and drift apart, which is how this whole
         family of bug starts.
      2. Every key that call site sends is a field the Rust patch knows. It is
         `deny_unknown_fields` on purpose, so `assistant_name` instead of
         `assistantName` is a hard error at runtime -- better than being
         accepted and ignored, and better still caught here, without a build.

    Read from the two files rather than restated, so a rename in either one is
    caught rather than described.
    """
    import re
    problems = []

    calls = list(re.finditer(r"invoke\(\s*['\"]save_profile['\"]", html))
    if len(calls) != 1:
        problems.append(f"save_profile is invoked {len(calls)} times; there must be "
                        "exactly one route, or Save and Finish can send different "
                        "field sets")
        return problems

    # The object literal passed as `profile:`, up to its closing brace.
    tail = html[calls[0].end():calls[0].end() + 2000]
    body = re.search(r"profile:\s*\{(.*?)\}", tail, re.S)
    if not body:
        problems.append("could not find the profile object the window posts — this "
                        "check has gone blind and is not a pass")
        return problems
    sent = set(re.findall(r"(\w+)\s*:", body.group(1)))

    rs = (HERE / "src-tauri" / "src" / "profile.rs").read_text(errors="replace")
    decl = re.search(r"pub struct ProfilePatch \{(.*?)\n\}", rs, re.S)
    if not decl:
        problems.append("ProfilePatch not found in profile.rs — the window's save "
                        "no longer has a backend contract this can check against")
        return problems
    known = set()
    for f in re.findall(r"pub (\w+):\s*Option<", decl.group(1)):
        head, *rest = f.split("_")
        known.add(head + "".join(w.capitalize() for w in rest))

    for key in sorted(sent - known):
        problems.append(f"the window posts {key!r}, which ProfilePatch does not "
                        "accept — deny_unknown_fields will refuse the whole save")
    return problems


def check_setup_style_step(html):
    """Q7's three taps must do something, and must not promise a count.

    Beck's F2 and F3. The taps used to be discarded whenever the field was
    non-empty -- which, on any run after the first, means whenever the wizard
    itself had filled it in. So reopening setup to change your style did
    nothing and said nothing.
    """
    import re
    problems = []
    if "STYLE_LINES" not in html or "function styleIsOurs" not in html:
        problems.append("the setup style step no longer recognises its own output "
                        "(STYLE_LINES / styleIsOurs missing) — reopening setup to "
                        "change your style is silently doing nothing again")
    if re.search(r"hint:\s*'Three taps", html):
        problems.append("Q7 still promises 'Three taps' while Finish is enabled "
                        "with zero — the copy is asking for something it does not "
                        "require")
    return problems


def main():
    SHOTS.mkdir(exist_ok=True)
    html = (HERE / "ui" / "index.html").read_text(errors="replace")
    source_problems = check_profile_save(html) + check_setup_style_step(html)
    if source_problems:
        print("FAIL: the window and the backend disagree about a save:")
        for c in source_problems:
            print(f"  - {c}")
        return 1
    css_problems = check_css_comments(
        (HERE / "ui" / "index.html").read_text(errors="replace"))
    if css_problems:
        print("FAIL: unbalanced CSS comments — a rule is being silently eaten:")
        for c in css_problems:
            print(f"  - {c}")
        return 1

    port = free_port()
    dport = free_port()
    serve(port)

    proc = subprocess.Popen(
        ["/snap/bin/chromium", "--headless=new", f"--remote-debugging-port={dport}",
         f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}", "--hide-scrollbars",
         "--no-first-run", "--no-default-browser-check",
         # NOT OPTIONAL, and it fails in a confusing way without it: Chromium
         # rejects the CDP websocket handshake with a bare 403 that looks like
         # "could not attach" rather than like an origin check.
         "--remote-allow-origins=*",
         "--user-data-dir=/home/mdalton/.cache/nameos-render-check",
         "--enable-unsafe-swiftshader",   # headless has no real GPU
         f"http://127.0.0.1:{port}/index.html"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    fails = []
    # Set BEFORE the try, not inside it: if something dies before `note()`'s
    # own section even starts (a CDP connect failure, say), the crash-report
    # code below still has a real number to print instead of a NameError
    # masking the actual traceback.
    checked = 0
    # THE SCAR THIS IS FOR: on 2026-08-27 `addApi` was removed from the page
    # and this file died at what is now the "connectors, brain form" section
    # with a bare TypeError -- and because every diagnostic print used to sit
    # in one block at the very end (below `finally:`), that crash produced
    # NOTHING: no assertion result, no "here is how far it got", just a
    # non-zero exit that looked identical to any other day's non-zero exit.
    # It sat that way for a day before a human noticed by accident. `note()`
    # above already prints as each section finishes; this catches whatever
    # note() did NOT get to reach, so a crash always says which of the
    # numbered sections it got through and where it actually died.
    crash_tb = None
    try:
        cdp = CDP(dport)
        cdp.connect()
        cdp.send("Runtime.enable")
        cdp.send("Page.enable")

        # A PLAIN BROWSER IS NOT TAURI, so every invoke() throws and the whole
        # app renders as if nothing works — no folder, no connectors, and an
        # indicator stuck on its default. Stubbing __TAURI__ before the document
        # runs is what lets these surfaces be photographed at all.
        #
        # THE STUB RETURNS DELIBERATELY MIXED STATE — one connector that has
        # passed a real test, one that has not, one that failed — because the
        # whole point of the indicator is that those three look different. A
        # stub where everything works would photograph beautifully and prove
        # nothing.
        cdp.send("Page.addScriptToEvaluateOnNewDocument", source=r"""
          window.__TAURI__ = { core: { invoke: async (cmd, args) => {
            if (cmd === 'default_workdir') return 'C:\\Users\\mdalt\\Documents\\NameOS';
            if (cmd === 'is_folder') return true;
            if (cmd === 'preflight') return window.__pf || { ready: true, version: 'stub' };
            if (cmd === 'install_claude') return window.__inst || { ok:true };
            if (cmd === 'scan_notes') return { nodes: [], edges: [], truncated: false };
            if (cmd === 'load_profile') return window.__prof || { about:'', goal:'', memory:'', assistantName:'Jarvis', personality:'', wakeWord:'' };
            if (cmd === 'save_profile') { window.__saved = args; return 'C:\\Users\\mdalt\\Documents\\NameOS\\CLAUDE.md'; }
            if (cmd === 'sync_profile') return null;
            // THE VOICE CARD. Captured rather than discarded, because the whole
            // point of this pass is that answering a question REACHES the model
            // -- a stub that swallowed it would let the wiring rot invisibly,
            // which is the exact fault ("nothing reads them") being fixed.
            if (cmd === 'save_voice_card') { window.__card = args.card; return 'C:\\Users\\mdalt\\Documents\\NameOS\\CLAUDE.md'; }
            // "Hear the difference". Returns a DIFFERENT pair, not two copies
            // of one string -- a stub where both drafts matched would
            // photograph beautifully and prove nothing about the one claim the
            // panel makes. window.__pairFail forces the failure path, because
            // "the pair is cleared and the error shows" is the behaviour worth
            // testing and it is the one that never happens by accident.
            if (cmd === 'hear_the_difference') {
              if (window.__pairFail) throw new Error('stub: the brain did not answer');
              window.__pairArgs = args;
              return { without: 'A stub draft written with nothing to go on.',
                       with: 'A stub draft written with the card, and it runs its clauses on, '
                           + 'the way they do, rather than stopping and starting again',
                       subject: args.subject };
            }
            // UPDATES. Driven from window.__upd so one page can be photographed
            // in both states -- an update waiting, and genuinely up to date.
            // A stub that only ever says "up to date" would photograph the
            // empty case and prove nothing about the one that matters.
            if (cmd === 'check_update') return window.__upd
              || { available: false, currentVersion: '0.1.0' };
            if (cmd === 'is_running') return !!window.__running;
            if (cmd === 'install_update') throw new Error('stub: not installing');
            if (cmd === 'list_connectors') return [
              { id:'a', kind:'api', name:'OpenAI', provider:'openai', baseUrl:'', model:'gpt-5',
                args:[], connected:true, checkedAt:String(Math.floor(Date.now()/1000)-120),
                lastError:'', hasSecret:true },
              { id:'b', kind:'api', name:'Anthropic', provider:'anthropic', baseUrl:'', model:'',
                args:[], connected:false, checkedAt:'', lastError:'', hasSecret:false },
              { id:'c', kind:'mcp', name:'Filesystem', provider:'', command:'npx',
                args:['-y','@modelcontextprotocol/server-filesystem','.'],
                connected:false, checkedAt:String(Math.floor(Date.now()/1000)-9000),
                lastError:'The server started but did not answer in time.', hasSecret:false },
            ];
            // THE TWO BRAIN SECTIONS AT THE TOP OF APPS -- dcaec31, 2026-08-28.
            // Without this stub `invoke('recommended_ai')` RESOLVES to null
            // rather than rejecting, `RECO_AI.cloud` a line later throws out of
            // an async function nobody awaits, and renderRecommendedAi() gives
            // up silently -- the two sections just never paint, with no error
            // anywhere a screenshot or a console log would catch. That is
            // exactly the shape design-shots.py had until the same commit
            // fixed it there; this file never had the stub to lose. Values
            // copied from CLOUD_AI/LOCAL_AI in brain_setup.rs, same as
            // design-shots.py's, so a drift between the two capture tools
            // would show up as a real assertion failure rather than nothing.
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
            return null;
          } }, event: { listen: () => {} } };
        """)
        cdp.send("Page.reload")
        time.sleep(1.5)

        def shot(name):
            png = cdp.send("Page.captureScreenshot", format="png")["data"]
            p = SHOTS / name
            p.write_bytes(base64.b64decode(png))
            return p

        # THE WHOLE REASON THIS FILE WAS DEAD FOR A DAY WITH NOBODY NOTICING:
        # every print() below used to happen in one block at the very end (see
        # the tail of main()), so an exception anywhere in the file — like the
        # addApi TypeError that killed this run on 2026-08-27 — produced ZERO
        # output before the traceback. `note()` prints as each section
        # actually finishes, flushed immediately, so a crash three sections
        # from the end still leaves a trail showing exactly how far it got.
        # It is not a second assertion mechanism — it never touches `fails` —
        # just a heartbeat this file did not have. (`checked` is set before
        # this try block starts, not here — see the comment by its init.)
        def note(label):
            nonlocal checked
            checked += 1
            print(f"  [{checked:02d}] {label}", flush=True)

        # THE SIGN-IN SCREEN IS PART OF THE PRODUCT, so it gets checked like
        # one. The ring lives outside #app precisely so it is already running
        # here; if it ever gets moved back inside, this is the shot that fails.
        time.sleep(INTRO_SETTLE_S)
        signin = shot("nameos-ring-signin.png")
        signin_lit = lit_fraction(signin)
        if signin_lit < 0.004:
            fails.append(f"no ring behind the sign-in screen (only "
                         f"{signin_lit:.4%} of the frame is lit) — the first "
                         "thing anyone sees is a flat black rectangle")
        note("sign-in ring")

        # Now sign in. #authGate is the real overlay and it covers the whole
        # window; hiding it and unhiding #app is exactly what signIn() does.
        shown = cdp.js("""(() => {
          const g = document.getElementById('authGate');
          const a = document.getElementById('app');
          if (g) g.hidden = true;
          if (a) a.hidden = false;
          return !!(g && a);
        })()""")
        if not shown:
            fails.append("#authGate / #app not found — the page did not load as "
                         "expected, so nothing below proves anything")

        # Require the module to have actually mounted. A missing bridge means
        # the import failed -- exactly the silent failure a screenshot hides.
        time.sleep(1.2)
        if not cdp.js("!!(window.RiftBrain && window.RiftBrain.bump)"):
            fails.append("window.RiftBrain.bump missing — aurelia-mount.js did "
                         "not load (check the console / vendor paths)")

        idle = shot("nameos-ring-idle.png")

        # IS IT ACTUALLY DRAWING? A black frame and a dead module look the same.
        #
        # MEASURE THE SCREENSHOT, NOT THE CANVAS. The obvious check —
        # drawImage(canvas) into a 2D context and count lit pixels — reads back
        # ALL ZEROS from a healthy WebGL canvas, because three.js does not set
        # preserveDrawingBuffer and the buffer is cleared after compositing. It
        # cost a false "the ring is not rendering" on a render that was perfect.
        # The compositor's own screenshot has no such problem.
        lit = lit_fraction(idle)
        if lit < 0.004:
            fails.append(f"the ring is not rendering — only {lit:.4%} of the "
                         "frame is lit, which is a black window")
        note("idle ring + app mount")

        # POINTER. Move into the open ground, away from rail/topbar/chat panel.
        cx, cy = int(VIEWPORT[0] * 0.42), int(VIEWPORT[1] * 0.40)
        for ev in ("mouseMoved",):
            cdp.send("Input.dispatchMouseEvent", type=ev, x=cx, y=cy, button="none")
        cdp.send("Input.dispatchMouseEvent", type="mouseMoved",
                 x=cx + 6, y=cy + 6, button="none")
        time.sleep(1.6)
        hover = shot("nameos-ring-pointer.png")
        reached = cdp.js("""(() => {
          const c = document.getElementById('brainCanvas');
          const r = c.getBoundingClientRect();
          const el = document.elementFromPoint(%d, %d);
          return el === c || c.contains(el);
        })()""" % (cx, cy))
        if not reached:
            fails.append("pointer does not reach #brainCanvas — something is "
                         "covering it, so the ring cannot answer the cursor")
        note("pointer")

        # SPEECH. Exactly what speak()'s onboundary handler does, repeated at
        # roughly a spoken word's pace — one bump and an instant screenshot
        # would photograph a rise that has had three frames to happen, and the
        # scene eases its cursor uniform at 0.09/frame on purpose.
        cdp.js("""(() => {
          window.RiftBrain.setSpeaking(true);
          window.__t = setInterval(() => window.RiftBrain.bump(0.55 + Math.random() * 0.45), 260);
          return true;
        })()""")
        time.sleep(1.4)
        talking = shot("nameos-ring-talking.png")
        cdp.js("clearInterval(window.__t); window.RiftBrain.setSpeaking(false);")

        # DOES SPEECH ACTUALLY CHANGE THE PICTURE? A bump that moves no pixels
        # is a hook that is wired to nothing.
        talk_lit = lit_fraction(talking)
        if talk_lit <= lit:
            fails.append(f"speech does not brighten the ring (idle {lit:.4%} -> "
                         f"talking {talk_lit:.4%}) — the bump is not reaching "
                         "the scene")
        note("speech bump")

        # THE CONNECTORS VIEW and the indicator that summarises it.
        cdp.js("document.getElementById('connChip').click()")
        time.sleep(1.0)
        conn = shot("nameos-connectors.png")
        # The indicator must read GREEN off the stub's one genuinely-tested
        # connector, and AMBER if that one is taken away. Both are asserted,
        # because a dot that is always green passes a screenshot check.
        # THE DOT MEANS CLAUDE. Mark, 2026-08-26: "the icon for nameos to be
        # green when claude is connected". The first version read off the
        # connectors list and sat grey on a machine where Claude was working —
        # so both directions are asserted here, not just the happy one.
        green = cdp.js("document.getElementById('connDot').classList.contains('ok')")
        label = cdp.js("document.getElementById('connLabel').textContent")
        if not green:
            fails.append("indicator is not green while Claude is connected")
        if not (label or "").startswith("Claude"):
            fails.append(f"indicator says {label!r}; it should name Claude")

        # And it must go RED when Claude is not there — a light that is always
        # green is not a light.
        red = cdp.js("""(() => {
          claudeState = { ready:false, problem:'missing', detail:'not on PATH' };
          paintIndicator(); renderConnectors();
          const d = document.getElementById('connDot');
          return d.classList.contains('bad') &&
                 /Claude/.test(document.getElementById('connLabel').textContent);
        })()""")
        if not red:
            fails.append("indicator does not go red and name Claude when "
                         "Claude Code is missing")

        # Claude is the first row of the view, and it has no Remove.
        first = cdp.js("""(() => {
          claudeState = { ready:true, version:'2.0.1', path:'/usr/bin/claude' };
          paintIndicator(); renderConnectors();
          const row = document.querySelector('#connList .connRow');
          if (!row) return 'no rows';
          return JSON.stringify({
            name: row.querySelector('.connName span').textContent,
            buttons: [...row.querySelectorAll('.connBtns button')].map(b => b.textContent),
          });
        })()""")
        f0 = json.loads(first) if first and first.startswith("{") else {}
        if f0.get("name") != "Claude Code":
            fails.append(f"first row of Connections is {f0.get('name')!r}, not Claude Code")
        if "Remove" in (f0.get("buttons") or []):
            fails.append("Claude Code has a Remove button; it is not the user's to delete")
        # THE FORM MUST SHOW ONLY THE FIELDS THAT APPLY -- still the rule, but
        # not the same form any more. `addApi` and the fApiRow/fProviderWrap it
        # toggled are gone: 6393262 (2026-08-28) took every cloud provider kind
        # out of this sheet, and 2cb918d (2026-08-27) had already removed the
        # button itself, which is what killed this file for a day (see the
        # header). "Add your own server" now produces exactly one shape -- an
        # MCP command line, never a key, an address or a provider picker -- so
        # the `display:flex` beats `[hidden]` trap this block used to catch on
        # the API/MCP toggle is caught here on what actually still toggles.
        cdp.js("document.getElementById('addMcp').click()")
        time.sleep(0.4)
        connform = shot("nameos-connector-form.png")
        shown_mcp = json.loads(cdp.js("""(() => {
          const vis = id => { const e = document.getElementById(id);
                              return !!(e && e.offsetParent !== null); };
          return JSON.stringify({ mcp: vis('fMcpRow'), url: vis('fUrlRow'),
                                  key: vis('fKeyRow'), acct: vis('fAcctRow') });
        })()""") or "{}")
        if not shown_mcp.get("mcp"):
            fails.append("'Add your own server' does not show the command/"
                         "argument fields")
        if shown_mcp.get("url") or shown_mcp.get("key") or shown_mcp.get("acct"):
            fails.append(f"a fresh MCP server form shows fields it has no "
                         f"answer for yet (address/key/account): {shown_mcp}")
        cdp.js("document.getElementById('connCancel')?.click()")
        time.sleep(0.3)

        # ADDING A BRAIN MOVED TO ITS OWN SHEET -- Mark, 2026-08-27: "can we
        # make the connector universal ... claude, or local hermes agent."
        # Since 6393262 (2026-08-28) the only kind `provForm` can produce is
        # `local`, so the same hidden-field discipline now means the API key
        # row must STAY hidden (Ollama takes no key) while address and model
        # stay visible -- the inverse shape of the check above, on the form
        # that actually replaced the old one.
        cdp.js("if (window.openBrainSheet) window.openBrainSheet('brain');")
        time.sleep(0.6)
        cdp.js("document.getElementById('addProv').click()")
        time.sleep(0.4)
        brainform = shot("nameos-brain-form.png")
        provshown = json.loads(cdp.js("""(() => {
          const vis = id => { const e = document.getElementById(id);
                              return !!(e && e.offsetParent !== null); };
          return JSON.stringify({ name: vis('pName'), url: vis('pUrl'),
                                  model: vis('pModel'), key: vis('pKeyRow') });
        })()""") or "{}")
        if not (provshown.get("name") and provshown.get("url") and provshown.get("model")):
            fails.append(f"'Add another brain' is missing one of its own "
                         f"fields: {provshown}")
        if provshown.get("key"):
            fails.append("'Add another brain' shows an API key row for a "
                         "brain that can only be local")
        # Close the Brain sheet before reopening Apps below -- both are
        # `.sheet` overlays and leaving one hidden=false under the other is
        # harmless to the assertions that follow but makes the next
        # screenshot show two stacked dialogs for no reason.
        cdp.js("if (window.closeBrainSheet) window.closeBrainSheet();")
        time.sleep(0.3)

        # THE TWO BRAIN SECTIONS AT THE TOP OF APPS. dcaec31, 2026-08-28: with
        # no stub for `recommended_ai`, renderRecommendedAi() resolves to a
        # silent no-op (see the stub's own comment) and Cloud AI / Local AI
        # never paint, in every capture ever taken of this sheet -- design-
        # shots.py had this exact bug and fixed it the same commit; this file
        # never had the stub to lose, so it has never once proven the sections
        # paint. Proven here rather than merely looked at: the headings must
        # actually un-hide, and each grid must hold the one brain the product
        # still offers, under the name it actually ships with.
        # (Apps was already open from the connChip click above; connBtn's
        # opener is idempotent and re-reads providers, which is what a real
        # re-open of the sheet would do too.)
        cdp.js("document.getElementById('connBtn').click()")
        time.sleep(1.0)
        reco = json.loads(cdp.js("""(() => JSON.stringify({
          cloudHidden: document.getElementById('cloudAiHead').hidden,
          localHidden: document.getElementById('localAiHead').hidden,
          cloudTiles: document.getElementById('cloudAiGrid').children.length,
          localTiles: document.getElementById('localAiGrid').children.length,
          cloudName: document.querySelector('#cloudAiGrid .svcName')?.firstChild?.textContent,
          localName: document.querySelector('#localAiGrid .svcName')?.firstChild?.textContent,
        }))()""") or "{}")
        if reco.get("cloudHidden") or reco.get("localHidden"):
            fails.append("the Cloud AI / Local AI sections never un-hide -- "
                         "renderRecommendedAi() is not painting them")
        if reco.get("cloudTiles") != 1 or reco.get("localTiles") != 1:
            fails.append(f"expected exactly one cloud brain and one local "
                         f"brain tile, got {reco.get('cloudTiles')} cloud / "
                         f"{reco.get('localTiles')} local")
        if reco.get("cloudName") != "Claude" or reco.get("localName") != "Ollama":
            fails.append(f"brain tiles show the wrong names: "
                         f"cloud={reco.get('cloudName')!r} local={reco.get('localName')!r}")
        print(f"reco    : cloud={reco.get('cloudTiles')} local={reco.get('localTiles')} "
              f"({reco.get('cloudName')} / {reco.get('localName')})")
        print(f"form    : {connform}")
        print(f"brain   : {brainform}")
        cdp.js("document.getElementById('connSheetClose').click()")
        time.sleep(0.5)
        note("connectors, brain form, Cloud/Local AI tiles")

        # THE SETUP PANEL MUST NEVER SHOW A COMMAND. Mark, 2026-08-26: "don't
        # show the user the command as they dont care." Asserted on the RENDERED
        # panel, not on the source, because the source could stop containing it
        # while a template still builds it.
        setup = json.loads(cdp.js("""(() => {
          window.__pf = { ready:false, problem:'missing', path:'claude', detail:'program not found' };
          return check().then(() => {
            const box = document.querySelector('.setup');
            const text = box ? box.textContent : '';
            return JSON.stringify({
              shown: !!box,
              leaksCommand: /npm |install -g|@anthropic-ai/.test(text),
              hasCodeBlock: !!(box && box.querySelector('code')),
              buttons: box ? [...box.querySelectorAll('button')].map(b => b.textContent) : [],
            });
          });
        })()""") or "{}")
        if not setup.get("shown"):
            fails.append("no setup panel when Claude is missing")
        if setup.get("leaksCommand"):
            fails.append("the setup panel still shows the install command")
        if setup.get("hasCodeBlock"):
            fails.append("the setup panel still renders a copyable code block")
        if not any("Install" in b for b in (setup.get("buttons") or [])):
            fails.append(f"no install button on the setup panel: {setup.get('buttons')}")
        setupshot = shot("nameos-setup.png")

        # PRESSING "TRY AGAIN" MUST NOT STACK UP BUTTONS. It did: every
        # failure appended another offer, so three presses left three of them.
        repeat = json.loads(cdp.js("""(() => {
          window.__inst = { ok:false, problem:'failed', detail:'nope' };
          const box = document.querySelector('.setup');
          const press = () => {
            const go = [...box.querySelectorAll('button')].find(b => /Install|Try again/.test(b.textContent));
            if (go) go.click();
          };
          press();
          return new Promise(r => setTimeout(() => { press(); setTimeout(() => { press();
            setTimeout(() => r(JSON.stringify({
              buttons: [...box.querySelectorAll('button')].map(b => b.textContent),
              text: box.textContent,
            })), 500); }, 500); }, 500));
        })()""") or "{}")
        btns = repeat.get("buttons") or []
        if len(btns) != len(set(btns)):
            fails.append(f"pressing Try again stacks up duplicate buttons: {btns}")
        if any("Node" in b for b in btns):
            fails.append("still offering Node.js, which the native installer "
                         f"does not need: {btns}")
        if "npm" in (repeat.get("text") or "").lower():
            fails.append("the failure message leaks npm at the user")
        note("setup panel + repeated install presses")

        # Put it back so the rest of the run sees a healthy app.
        cdp.js("window.__pf = { ready:true, version:'stub' }; window.__inst = { ok:true };")
        cdp.js("check()")
        time.sleep(0.5)

        # "ABOUT YOU" — it opens, it says where the text lands BEFORE anyone
        # types, and saving actually carries all three fields plus the folder.
        cdp.js("document.getElementById('aboutBtn').click()")
        time.sleep(0.6)
        about = shot("nameos-about-you.png")
        # offsetParent IS ALWAYS NULL ON A position:fixed ELEMENT, so the usual
        # visibility trick reports every sheet in this app as closed. Measure the
        # box instead.
        aboutState = json.loads(cdp.js("""(() => {
          const vis = id => { const e = document.getElementById(id);
                              if (!e) return false;
                              const r = e.getBoundingClientRect();
                              return r.width > 0 && r.height > 0 &&
                                     getComputedStyle(e).visibility !== 'hidden'; };
          return JSON.stringify({
            open: vis('aboutSheet'),
            fields: ['askAbout','askGoal','askMemory'].every(vis),
            where: (document.getElementById('askWhere').textContent || '').trim(),
          });
        })()""") or "{}")
        if not aboutState.get("open"):
            fails.append("the About you panel does not open")
        if not aboutState.get("fields"):
            fails.append("About you is missing one of its three fields")
        if "CLAUDE.md" not in (aboutState.get("where") or ""):
            fails.append("About you does not say where the text is written "
                         f"before you type it (said {aboutState.get('where')!r})")

        # "ABOUT ME" — the second tab, the name field, and the presets, which
        # must FILL the box rather than merely being selected.
        preset = json.loads(cdp.js("""(() => {
          document.getElementById('tabMe').click();
          const chips = [...document.querySelectorAll('#presets .preset')];
          const before = document.getElementById('askPersonality').value;
          if (chips.length) chips[0].click();
          const after = document.getElementById('askPersonality').value;
          return JSON.stringify({
            paneShown: !document.getElementById('paneMe').hidden,
            chips: chips.map(c => c.textContent),
            filled: after.length > 40 && after !== before,
            hasName: !!document.getElementById('askName'),
          });
        })()""") or "{}")
        if not preset.get("paneShown"):
            fails.append("the About me tab does not switch panes")
        if len(preset.get("chips") or []) < 3:
            fails.append(f"too few personality presets: {preset.get('chips')}")
        if not preset.get("filled"):
            fails.append("pressing a personality preset does not fill the box "
                         "with editable text")
        if not preset.get("hasName"):
            fails.append("there is no name field")
        tabLook = json.loads(cdp.js("""(() => {
          const me = getComputedStyle(document.getElementById('tabMe'));
          const you = getComputedStyle(document.getElementById('tabYou'));
          return JSON.stringify({
            differs: me.color !== you.color ||
                     me.borderBottomColor !== you.borderBottomColor,
            boxed: me.backgroundColor !== 'rgba(0, 0, 0, 0)' &&
                   me.backgroundColor !== 'transparent',
          });
        })()""") or "{}")
        if not tabLook.get("differs"):
            fails.append("the selected tab looks identical to the unselected one")
        if tabLook.get("boxed"):
            fails.append("the tabs render as default grey buttons")
        aboutme = shot("nameos-about-me.png")

        cdp.js("document.getElementById('tabYou').click()")
        saved = json.loads(cdp.js("""(() => {
          document.getElementById('askAbout').value  = 'WHO';
          document.getElementById('askGoal').value   = 'GOAL';
          document.getElementById('askMemory').value = 'ALWAYS';
          document.getElementById('aboutForm').requestSubmit();
          return new Promise(r => setTimeout(() => r(JSON.stringify(window.__saved || {})), 600));
        })()""") or "{}")
        prof = (saved.get("profile") or {})
        if not (prof.get("personality") or "").strip():
            fails.append("the personality was dropped on save — switching tabs "
                         "must not lose the other pane")
        if [prof.get("about"), prof.get("goal"), prof.get("memory")] != ["WHO","GOAL","ALWAYS"]:
            fails.append(f"About you did not send all three fields on save: {prof}")
        if not saved.get("workdir"):
            fails.append("About you saved without the working folder, so it "
                         "would never reach a CLAUDE.md")
        note("About you / About me")

        # THE WAKE WORD. Mark, 2026-08-26: the mic listens by default for a
        # trigger word the user defines, and it defaults to the name.
        wake = json.loads(cdp.js("""(() => {
          const r = {};
          // Falls back to the name when the field is blank.
          document.getElementById('askWake').value = '';
          document.getElementById('askName').value = 'Jarvis';
          r.fallsBackToName = currentWakeWord() === 'Jarvis';
          // An explicit phrase wins.
          document.getElementById('askWake').value = 'hey computer';
          r.explicitWins = currentWakeWord() === 'hey computer';
          // Only what comes AFTER the word is taken, and it must not fire on a
          // word that merely contains it.
          r.after      = afterWake('hey computer, write me a note', 'hey computer');
          r.notCalled  = afterWake('the weather is fine', 'hey computer');
          r.bareName   = afterWake('Jarvis', 'jarvis');
          r.caseBlind  = afterWake('JARVIS do the thing', 'jarvis');
          // THE MISHEARINGS. These are the exact renderings the voice line
          // measured, and the reason an exact match "does not work".
          r.mishears   = ['jervis','garvis','darvis','harvis','marvis','javis','jarviss']
                           .map(w => afterWake(w + ' do it', 'jarvis'));
          // ...and the ones that must NOT wake it.
          r.jars       = afterWake('put it in the jars please', 'jarvis');
          r.ratios     = { jervis: wakeRatio('jervis','jarvis'),
                           jars:   wakeRatio('jars','jarvis'),
                           travis: wakeRatio('travis','jarvis') };
          // THE ANCHOR: after the name alone, the next sentence needs no name.
          anchorArm();
          r.anchorOpen = Date.now() < anchorUntil;
          r.anchorOnce = anchorTake() && !anchorTake();
          return JSON.stringify(r);
        })()""") or "{}")
        if not wake.get("fallsBackToName"):
            fails.append("the wake word does not fall back to the name")
        if not wake.get("explicitWins"):
            fails.append("an explicit wake word does not override the name")
        if wake.get("after") != "write me a note":
            fails.append(f"wrong text taken after the wake word: {wake.get('after')!r}")
        if wake.get("notCalled") is not None:
            fails.append("speech without the wake word is being acted on")
        if any(v != "do it" for v in (wake.get("mishears") or [None])):
            fails.append(f"common mishearings of the name do not wake it: "
                         f"{wake.get('mishears')} — this is what 'the trigger "
                         f"word does not work' actually means")
        if wake.get("jars") is not None:
            fails.append("'jars' wakes it — the length floor is not holding")
        rt = wake.get("ratios") or {}
        if abs((rt.get("jervis") or 0) - 0.8333) > 0.002 or abs((rt.get("jars") or 0) - 0.8) > 0.002:
            fails.append(f"the ratio does not reproduce the voice line's measured "
                         f"figures: {rt}")
        if not wake.get("anchorOpen"):
            fails.append("saying the name alone does not open the follow-up window")
        if not wake.get("anchorOnce"):
            fails.append("the follow-up window is not consumed — one name should "
                         "admit one utterance")
        if wake.get("bareName") != "":
            fails.append(f"saying just the name should wait, not send: {wake.get('bareName')!r}")
        if wake.get("caseBlind") != "do the thing":
            fails.append("the wake word is case-sensitive")
        note("wake word")

        # THE INFO BUTTON AND ITS NAME SUGGESTIONS.
        ideas = json.loads(cdp.js("""(() => {
          document.getElementById('tabMe').click();
          const box = document.getElementById('nameIdeas');
          const before = !box.hidden;
          document.getElementById('nameInfo').click();
          const names = [...document.querySelectorAll('#namePresets .preset')].map(b => b.textContent);
          // Clear BOTH: an explicit wake word from an earlier check correctly
          // outranks the name, which made this assertion fail for the right
          // reason and the wrong one.
          document.getElementById('askName').value = '';
          document.getElementById('askWake').value = '';
          if (names.length) document.querySelector('#namePresets .preset').click();
          return JSON.stringify({
            startsHidden: !before,
            opens: !box.hidden,
            names,
            fills: document.getElementById('askName').value,
            wakeFollows: currentWakeWord(),
          });
        })()""") or "{}")
        if not ideas.get("startsHidden"):
            fails.append("the name suggestions are open before the info button is pressed")
        if not ideas.get("opens"):
            fails.append("the info button does not reveal the name suggestions")
        if len(ideas.get("names") or []) < 6:
            fails.append(f"too few name suggestions: {ideas.get('names')}")
        if not ideas.get("fills"):
            fails.append("pressing a suggested name does not fill the name field")
        if ideas.get("wakeFollows") != ideas.get("fills"):
            fails.append("picking a name does not become the wake word")

        # NO SHELL IN THE CONVERSATION. Mark, twice: "don't show the user the
        # command as they dont care", then "showing alot of powershell commands
        # in chat". Asserted on what the chip RENDERS, not on the source.
        tools = json.loads(cdp.js("""(() => {
          const cases = [
            ['Bash', { command: 'powershell -NoProfile -Command "Get-ChildItem C:\\\\Users"' }],
            ['Bash', { command: 'cd /home/x && grep -rn needle .' }],
            ['Bash', { command: 'npm install -g @anthropic-ai/claude-code' }],
            ['Bash', { command: 'some-unknown-binary --flag' }],
            ['Read', { file_path: 'C:\\\\Users\\\\mdalt\\\\Documents\\\\NameOS\\\\Start here.md' }],
            ['WebFetch', { url: 'https://example.com/a/b' }],
          ];
          return JSON.stringify(cases.map(([n, i]) => toolLine(n, i)));
        })()""") or "[]")
        want = ['Listed files', 'Searched', 'Installed something', 'Ran a command',
                'Read Start here.md', 'Read example.com']
        got = [x.get('label') for x in tools]
        if got != want:
            fails.append(f"tool lines are not plain language: got {got}, wanted {want}")
        # And the raw text must survive on the tooltip rather than be thrown away.
        if not all(x.get('detail') for x in tools[:5]):
            fails.append("the exact command is not kept on the tooltip")
        # The rendered chip must contain no shell at all.
        leak = cdp.js("""(() => {
          addTool('Bash', { command: 'powershell -NoProfile -Command Get-ChildItem' });
          const chips = [...document.querySelectorAll('#feed .tool')];
          const last = chips[chips.length - 1];
          return last ? last.textContent : '';
        })()""")
        if any(w in (leak or "").lower() for w in ("powershell", "-command", "get-childitem")):
            fails.append(f"the chip still renders the shell command: {leak!r}")
        note("name suggestions + tool-line plain language")

        # THE VOICE PICKER. Ranking alone cannot fix a machine that only has
        # mechanical voices, so it must SAY that rather than quietly picking the
        # least bad one.
        vp = json.loads(cdp.js("""(() => {
          const legacyOnly = [
            { name: 'Microsoft David Desktop', lang: 'en-US', localService: true, default: true },
            { name: 'Microsoft Zira Desktop',  lang: 'en-US', localService: true },
          ];
          const orig = speechSynthesis.getVoices;
          speechSynthesis.getVoices = () => legacyOnly;
          paintVoices();
          const warned = !document.getElementById('voiceThin').hidden;
          const options = [...document.getElementById('askVoice').options].map(o => o.value);
          // Zira over David when those are the only two.
          localStorage.removeItem('nameos_voice');
          const ranked = pickVoice() && pickVoice().name;
          // An explicit choice must beat the ranking.
          localStorage.setItem('nameos_voice', 'Microsoft David Desktop');
          const explicit = pickVoice() && pickVoice().name;
          localStorage.removeItem('nameos_voice');
          speechSynthesis.getVoices = orig;
          return JSON.stringify({ warned, options, ranked, explicit });
        })()""") or "{}")
        if not vp.get("warned"):
            fails.append("with only legacy voices available, the app does not say so")
        if "" not in (vp.get("options") or []):
            fails.append("the voice list has no automatic option")
        if "Zira" not in (vp.get("ranked") or ""):
            fails.append(f"the ranking prefers the harsher legacy voice: {vp.get('ranked')!r}")
        if "David" not in (vp.get("explicit") or ""):
            fails.append("an explicitly chosen voice does not override the ranking")

        # IT MUST NOT HEAR ITSELF. Always-on mic plus spoken replies is a
        # feedback loop: it hears its own answer, the follow-up window is open
        # because it just answered, and it types its own words into the prompt.
        selfhear = json.loads(cdp.js("""(() => {
          wakeArmed = true;
          suspendHearing();
          const s = hearingSuspended;
          resumeHearing();
          return JSON.stringify({ suspends: s, resumesFlagCleared: !hearingSuspended });
        })()""") or "{}")
        if not selfhear.get("suspends"):
            fails.append("the microphone is not suspended while it speaks — it "
                         "will hear its own reply and answer itself")
        if not selfhear.get("resumesFlagCleared"):
            fails.append("the microphone never resumes after speaking")

        # A BETTER VOICE THAN THE DEFAULT.
        voice = json.loads(cdp.js("""(() => {
          const fake = [
            { name: 'Microsoft David Desktop', lang: 'en-US', localService: true, default: true },
            { name: 'Microsoft Aria Online (Natural) - English (United States)', lang: 'en-US', localService: false },
          ];
          const orig = speechSynthesis.getVoices;
          speechSynthesis.getVoices = () => fake;
          const picked = pickVoice();
          speechSynthesis.getVoices = orig;
          return JSON.stringify({ picked: picked && picked.name });
        })()""") or "{}")
        if "Natural" not in (voice.get("picked") or ""):
            fails.append(f"the voice picker takes the default robotic voice over "
                         f"a natural one: {voice.get('picked')!r}")

        # It must NEVER arm with nothing to listen for — a hot microphone with
        # no trigger is the one state this cannot sit in.
        #
        # THIS USED TO MEAN "clearing both fields must clear wakeArmed", and
        # that broke here first: currentWakeWord() gained a third fallback
        # after the field check above was written — Mark, 2026-08-27/28,
        # reporting TWICE that "mic was not activated by default" until it
        # was made to fall back to currentTheme().assistantName (Jarvis, on
        # this build) rather than sit empty pre-naming. So a blank name and a
        # blank wake field now legitimately leave it armed, on the theme's own
        # name — that is the fix working, not a bug. The invariant that
        # actually matters survives unchanged: if it is armed, there is
        # something real to listen for. Checking the pair together is what
        # tells "the fallback is doing its job" apart from "it went back to
        # arming on nothing", which `wakeArmed` alone cannot.
        armed = json.loads(cdp.js("""(() => {
          document.getElementById('askWake').value = '';
          document.getElementById('askName').value = '';
          refreshWake();
          return JSON.stringify({ armed: wakeArmed, word: currentWakeWord() });
        })()""") or "{}")
        if armed.get("armed") and not (armed.get("word") or "").strip():
            fails.append("the mic stays armed with no wake word to listen for "
                         "-- not even the theme's own fallback name")
        if not armed.get("armed"):
            fails.append(f"clearing the name field disarmed the mic instead of "
                         f"falling back to the theme's name (got {armed.get('word')!r})")
        note("voice picker + self-hear guard")

        # THE WORKING FOLDER MUST NOT BE IN THE TOP BAR ANY MORE, and must show
        # its NAME rather than the path. Asserted rather than eyeballed, because
        # this is the specific thing Mark asked about.
        folder = cdp.js("""(() => {
          const cwd = document.getElementById('cwd');
          const bar = document.getElementById('folderBar');
          const name = document.getElementById('folderName');
          return JSON.stringify({
            cwdVisible: !!(cwd && cwd.offsetParent !== null),
            barVisible: !!(bar && bar.offsetParent !== null),
            label: name ? name.textContent : null,
            title: bar ? bar.title : null,
          });
        })()""")
        f = json.loads(folder or "{}")
        if f.get("cwdVisible"):
            fails.append("the raw path box is still visible in the top bar")
        if not f.get("barVisible"):
            fails.append("the working-folder control is not visible anywhere")
        if f.get("label") != "NameOS":
            fails.append(f"folder shows {f.get('label')!r}, expected the folder "
                         "NAME 'NameOS' rather than a path")

        # THE WORDMARK IS A REAL BUTTON AND MUST NOT LOOK LIKE ONE.
        #
        # THE SCAR, 2026-08-27: a stray `*/` closed a CSS comment that was
        # already closed, so the orphaned prose after it was parsed as a
        # SELECTOR and swallowed the `.mark` rule whole. Every assertion in this
        # file still passed -- the button worked perfectly, it just rendered as
        # a grey pill in the corner of the app. **A broken comment does not
        # throw; it silently eats the next rule.** Only the screenshot caught
        # it, and only because somebody looked at it.
        mk = cdp.js("""(() => {
          const m = document.getElementById('markBtn');
          if (!m) return null;
          const c = getComputedStyle(m);
          return { bg: c.backgroundColor, border: c.borderTopWidth,
                   cursor: c.cursor, weight: c.fontWeight };
        })()""")
        if not mk:
            fails.append("#markBtn is missing — there is no way to reach the "
                         "update sheet when no update is waiting")
        else:
            if mk["bg"] not in ("rgba(0, 0, 0, 0)", "transparent"):
                fails.append(f"the NameOS wordmark has a background ({mk['bg']}) — "
                             "the .mark rule is not being applied, which usually "
                             "means a CSS comment above it is unbalanced")
            if mk["border"] != "0px":
                fails.append(f"the wordmark is drawing a border ({mk['border']})")
            if mk["cursor"] != "pointer":
                fails.append("the wordmark does not look clickable")
        note("folder control + wordmark")

        # --- UPDATES -------------------------------------------------------
        #
        # THE ONE THAT MATTERS IS THE CHIP BEING ABSENT. Mark's rule is that an
        # update indicator is invisible when there is nothing to say, and a
        # control that is always there is furniture. That is trivially easy to
        # regress by "tidying up" a hidden attribute, and impossible to notice
        # by looking at a screenshot of the good case.
        u0 = cdp.js("""(() => {
          const c = document.getElementById('updateChip');
          return { present: !!c, hidden: c ? c.hidden : null };
        })()""")
        if not u0.get("present"):
            fails.append("#updateChip is missing entirely")
        elif not u0.get("hidden"):
            fails.append("the update chip is visible with no update available — "
                         "it is meant to be invisible unless there is one")

        # Up to date: the sheet must SAY so rather than showing a blank panel.
        cdp.js("window.__upd = { available:false, currentVersion:'0.1.0' };")
        cdp.js("Updates.close(); Updates.check(true).then(()=>Updates.open())")
        time.sleep(1.0)
        upcur = shot("update-current.png")
        cur = cdp.js("""(() => ({
          open: !document.getElementById('updateSheet').hidden,
          headline: (document.getElementById('updHeadline').textContent||'').trim(),
          install: !document.getElementById('updInstall').hidden,
          chip: !document.getElementById('updateChip').hidden,
        }))()""")
        if not cur.get("open"):
            fails.append("the update sheet does not open")
        if "up to date" not in cur.get("headline", "").lower():
            fails.append(f"with no update, the sheet says {cur.get('headline')!r} "
                         "instead of saying it is up to date")
        if cur.get("install"):
            fails.append("the Install button is offered when there is nothing to install")
        if cur.get("chip"):
            fails.append("the update chip appears when there is no update")

        # An update waiting.
        cdp.js("""window.__upd = { available:true, currentVersion:'0.1.0',
          version:'0.2.0', date:'2026-08-27T10:00:00Z',
          notes:'Natural voices load faster.\\nConnections remember their last test.' };""")
        cdp.js("Updates.check(true)")
        time.sleep(1.0)
        upnew = shot("update-available.png")
        av = cdp.js("""(() => ({
          headline: (document.getElementById('updHeadline').textContent||'').trim(),
          notes: (document.getElementById('updNotes').textContent||'').trim(),
          notesShown: !document.getElementById('updNotes').hidden,
          install: !document.getElementById('updInstall').hidden,
          chip: !document.getElementById('updateChip').hidden,
          chipText: (document.getElementById('updateChipLabel').textContent||'').trim(),
        }))()""")
        if "0.2.0" not in av.get("headline", ""):
            fails.append(f"the new version is not named: {av.get('headline')!r}")
        if not av.get("install"):
            fails.append("no way to install an update that is available")
        if not av.get("chip"):
            fails.append("the update chip stays hidden when an update IS available")
        if "0.2.0" not in av.get("chipText", ""):
            fails.append(f"the chip does not name the version: {av.get('chipText')!r}")
        if not av.get("notesShown") or "voices" not in av.get("notes", ""):
            fails.append("the release notes are not shown")

        # NOTES ARE TEXT, NOT MARKUP. They come off the network, so this is the
        # check that a release note can never become script in the app.
        cdp.js("""window.__upd = { available:true, currentVersion:'0.1.0',
          version:'0.3.0', notes:'<img src=x onerror=\\'window.__pwned=1\\'>' };""")
        cdp.js("Updates.check(true)")
        time.sleep(0.8)
        if cdp.js("!!window.__pwned"):
            fails.append("release notes are rendered as HTML — a manifest can run "
                         "script inside the app")
        if cdp.js("!!document.querySelector('#updNotes img')"):
            fails.append("release notes are parsed as markup rather than shown as text")

        # Refuses to install over a run in flight.
        cdp.js("""window.__running = true;
          window.__upd = { available:true, currentVersion:'0.1.0', version:'0.2.0', notes:'x' };""")
        cdp.js("Updates.check(true)")
        time.sleep(0.6)
        cdp.js("document.getElementById('updInstall').click()")
        time.sleep(0.6)
        busy = cdp.js("(document.getElementById('updProblem').textContent||'').trim()")
        if "middle of something" not in busy:
            fails.append(f"the update installs over a run in flight (said {busy!r})")
        cdp.js("window.__running = false; Updates.close();")
        note("update sheet (up to date / available / notes / busy)")

        # "IN YOUR OWN WORDS" — the fourth Profile tab. Wren, 2026-08-28.
        # ~/Documents/Iris/2026-08-28-persona-interview-placement.md
        # Run LAST, deliberately: this section clears the pane's own storage
        # key and writes into #askPersonality, and earlier sections in this
        # file already assume things about both (the personality-preset check
        # at "About you / About me", the name/wake fields after it). Putting
        # this after every other section means nothing above it has to be
        # re-verified just because this one landed.
        ownwords = json.loads(cdp.js("""(async () => {
          const r = {};
          document.getElementById('aboutBtn').click();
          document.getElementById('tabWords').click();
          r.paneShown  = !document.getElementById('paneWords').hidden;
          r.formHidden = document.getElementById('aboutForm').hidden;
          r.saveHidden = document.getElementById('aboutSave').hidden;
          r.rowCount   = document.querySelectorAll('#ownGroups .ownQ').length;
          r.groupCount = document.querySelectorAll('#ownGroups .ownGroupName').length;

          // A clean slate makes this deterministic across runs and machines.
          localStorage.removeItem('nameos_ownwords_v1');
          document.getElementById('tabYou').click();
          document.getElementById('tabWords').click();
          r.coldCountHidden = document.getElementById('ownCount').hidden;

          const firstBtn = document.querySelector('#ownGroups .ownQBtn');
          firstBtn.click(); // expand
          r.expandedAria = firstBtn.getAttribute('aria-expanded') === 'true';
          const ta = document.querySelector('#ownGroups .ownBody textarea');
          r.hasTextarea = !!ta;
          r.hasMaxlength = ta.hasAttribute('maxlength');
          ta.value = 'this is a real test answer, long enough to show as an excerpt when the row collapses again';
          ta.dispatchEvent(new Event('input'));
          await new Promise(res => setTimeout(res, 550)); // clear the 400ms save debounce
          r.answeredClass = firstBtn.closest('.ownQ').classList.contains('answered');
          r.countVisible  = !document.getElementById('ownCount').hidden;
          r.countText     = document.getElementById('ownCount').textContent;
          const saved = JSON.parse(localStorage.getItem('nameos_ownwords_v1') || '{}');
          r.savedAnswerCount = Object.keys(saved.answers || {}).length;

          firstBtn.click(); // collapse
          const ex = firstBtn.querySelector('.ownQEx');
          r.excerptShown = !!(ex && ex.textContent.trim());

          r.hasFileInput = !!document.getElementById('ownFileInput');
          r.hasDirPicker = typeof window.showDirectoryPicker === 'function';
          r.pickFolderDisabled = document.getElementById('ownPickFolder').disabled;

          // ---- THE CARD ACTUALLY REACHES THE MODEL. This is the whole point
          // of the pass: eleven answers persisted and nothing read them.
          r.cardSent = window.__card || '';

          // ---- THE PAYOFF PANEL, all three of its states.
          // Cold: an invitation, no button, because a button that can only
          // fail is worse than no button.
          localStorage.removeItem('nameos_ownwords_v1');
          renderOwnWords();
          r.coldGoHidden   = document.getElementById('ownProofGo').hidden;
          r.coldBlockShown = !document.getElementById('ownBlocked').hidden;
          r.coldPairHidden = document.getElementById('ownPair').hidden;
          r.coldText = (document.getElementById('ownBlockedText')||{}).textContent || '';

          // Ready: ONE answer is enough. Iris's rule -- partial has to pay,
          // and a design that only works at eleven answers works for nobody.
          const one = document.querySelector('#ownGroups .ownQBtn');
          one.click();
          const ta2 = document.querySelector('#ownGroups .ownBody textarea');
          // DELIBERATELY A REAL-LENGTH, REAL-SHAPE ANSWER: run-on clauses, no
          // full stops, a typo left in. That is what Mark's own answers look
          // like in the vault, and it is the only input that exercises the
          // rhythm measurement -- ownVoiceCard() refuses to measure under 40
          // words on purpose, because a rhythm read off one line would be a
          // confident lie. A tidy one-liner here would have quietly proved
          // nothing about the part of the card that does the work.
          ta2.value = 'Leverage, unlock, synergy, anything that starts with in todays fast '
            + 'paced world, and I would never call a customer a partner because they are '
            + 'not one, they are paying me, and pretending otherwise is the kind of thing '
            + 'that makes people stop reading, so I do not do it and I would rather sound '
            + 'blunt than sound like everybody else does';
          ta2.dispatchEvent(new Event('input'));
          await new Promise(res => setTimeout(res, 550));
          r.readyGoShown  = !document.getElementById('ownProofGo').hidden;
          r.readyBlockHid = document.getElementById('ownBlocked').hidden;
          r.cardAfterOne  = window.__card || '';
          r.whatText = document.getElementById('ownProofWhat').textContent || '';

          // Pressed: a real pair, stacked, nothing highlighted.
          document.getElementById('ownProofBtn').click();
          await new Promise(res => setTimeout(res, 300));
          r.pairShown = !document.getElementById('ownPair').hidden;
          r.draftA = document.getElementById('ownDraftWithout').textContent || '';
          r.draftB = document.getElementById('ownDraftWith').textContent || '';
          r.pairNote = document.getElementById('ownPairNote').textContent || '';
          r.markCount = document.querySelectorAll('#ownPair mark, #ownPair .diff, #ownPair ins, #ownPair del').length;
          // Stacked, never side by side, at EVERY width -- Iris's decision.
          r.pairFlexDir = getComputedStyle(document.getElementById('ownPair')).flexDirection;
          r.cardPassed = (window.__pairArgs || {}).card || '';

          // Failed: the pair is CLEARED, not left stale under an error.
          window.__pairFail = true;
          document.getElementById('ownProofBtn').click();
          await new Promise(res => setTimeout(res, 300));
          r.failPairHidden = document.getElementById('ownPair').hidden;
          r.failDraft = document.getElementById('ownDraftWithout').textContent || '';
          r.failErrShown = !document.getElementById('ownProofErr').hidden;
          window.__pairFail = false;

          return JSON.stringify(r);
        })()""") or "{}")
        if not ownwords.get("paneShown"):
            fails.append("the Your words tab does not switch panes")
        if not ownwords.get("formHidden"):
            fails.append("#aboutForm stays visible on the Your words pane -- "
                         "#askWhere would bleed a CLAUDE.md sentence onto it, "
                         "same fault Iris's render already found once")
        if not ownwords.get("saveHidden"):
            fails.append("the Save button shows on Your words, where nothing goes through it")
        if ownwords.get("rowCount") != 11:
            fails.append(f"expected 11 question rows, got {ownwords.get('rowCount')}")
        if ownwords.get("groupCount") != 3:
            fails.append(f"expected 3 group headings, got {ownwords.get('groupCount')}")
        if not ownwords.get("coldCountHidden"):
            fails.append("the answered count shows with nothing answered -- "
                         "the flex-beats-[hidden] trap, hit a fifth time")
        if not ownwords.get("expandedAria"):
            fails.append("expanding a question does not set aria-expanded")
        if not ownwords.get("hasTextarea"):
            fails.append("expanding a question does not reveal a textarea")
        if ownwords.get("hasMaxlength"):
            fails.append("the answer box has a maxlength -- a short careful "
                         "answer is worthless here")
        if not ownwords.get("answeredClass"):
            fails.append("typing an answer does not mark the row answered")
        if not ownwords.get("countVisible"):
            fails.append("the answered count stays hidden after a real answer")
        ctext = ownwords.get("countText") or ""
        if "1 answered" not in ctext:
            fails.append(f"the count does not say what was actually answered: {ctext!r}")
        if re.search(r"\d+\s*(second|minute)", ctext, re.I):
            fails.append(f"a duration reached the count line: {ctext!r}")
        if ownwords.get("savedAnswerCount") != 1:
            fails.append("the answer was not persisted to localStorage")
        if not ownwords.get("excerptShown"):
            fails.append("collapsing an answered row loses the excerpt -- "
                         "coming back to this screen would be re-reading blind")
        if not ownwords.get("hasFileInput"):
            fails.append("there is no file input behind 'Choose files'")
        if ownwords.get("pickFolderDisabled") == ownwords.get("hasDirPicker"):
            fails.append("'Read from a folder' is enabled/disabled backwards "
                         "relative to whether this browser can actually do it")
        # ---- THE ANSWERS REACH THE MODEL. The gap this pass closes: eleven
        # answers persisted and nothing read them. save_voice_card is the only
        # thing that puts them in front of the model, so an answer that does
        # not fire it is the whole fault coming back.
        card = ownwords.get("cardSent") or ""
        if not card:
            fails.append("answering a question never pushed a voice card -- "
                         "the answers persist and nothing reads them, which is "
                         "the exact fault this was built to fix")
        if "real test answer" not in card:
            fails.append(f"the card does not carry what was actually answered: {card[:120]!r}")
        # The rhythm section is asserted against the REAL-LENGTH answer, not
        # the short excerpt one above -- ownVoiceCard() will not measure under
        # 40 words, which is correct and is why the seed there is long.
        after_one = ownwords.get("cardAfterOne") or ""
        if "Rhythm, counted from" not in after_one:
            fails.append(f"the card carries no measured rhythm -- the one part "
                         f"that is arithmetic rather than a model's summary: {after_one[:200]!r}")
        if "would never say" not in after_one:
            fails.append("the never-say list did not reach the card, and it is "
                         "the only instruction in the whole set that is binary")
        # EVERY CLAIM SIZED TO ITS EVIDENCE. Both of these were found by
        # rendering the card and reading it, and neither is cosmetic -- they
        # are the two ways a measurement lies confidently.
        #
        # The seed above is ONE unbroken run, which is the normal shape of a
        # real answer (Mark's own is a 73-word clause chain). Averaging one
        # sentence printed "run to about 61 words, and their longest goes to
        # 61" -- true, unreadable, and it would teach a model that every
        # sentence they write is sixty words long.
        if re.search(r"sentences run to about (\d+) words, and their longest goes to \1\b",
                     after_one):
            fails.append("the card averaged a single sentence against itself -- "
                         "a median of one thing is not a median")
        # And absence off 61 words is not evidence of a habit.
        for negative in ("No semicolons", "No dashes", "No exclamation marks",
                         "do not ask rhetorical questions"):
            if negative in after_one:
                fails.append(f"the card claims {negative!r} off a short sample -- "
                             f"most short passages contain none of those, so this "
                             f"is a confident negative with nothing behind it")
        if "counted from" not in after_one:
            fails.append("the card states a rhythm without saying how much was "
                         "measured -- a statistic with no n gets over-trusted")
        # THE SAMPLES NEVER TRAVEL. The card is built from an answer here, so
        # there is nothing pasted to leak -- but the assertion is cheap and it
        # is the line that matters most in the whole feature.
        if re.search(r"\bsample\b|\.eml\b", card):
            fails.append(f"a pasted sample looks to have reached the card: {card[:200]!r}")

        # ---- THE PAYOFF PANEL. Three states, and no fourth.
        if not ownwords.get("coldGoHidden"):
            fails.append("the payoff offers a button with nothing to compare -- "
                         "a button that can only fail is worse than no button")
        if not ownwords.get("coldBlockShown"):
            fails.append("the cold payoff state says nothing at all")
        if not ownwords.get("coldPairHidden"):
            fails.append("a draft pair shows with nothing answered -- a faked "
                         "proof of honesty, the worst screen this could ship")
        if re.search(r"pilot is not proof|In today's rapidly evolving",
                     ownwords.get("coldText") or ""):
            fails.append("the cold payoff state is showing drafted-looking text")
        if not ownwords.get("readyGoShown") or not ownwords.get("readyBlockHid"):
            fails.append("ONE answer does not unlock the payoff -- partial has "
                         "to pay, and a design that needs eleven works for nobody")
        if not ownwords.get("cardAfterOne"):
            fails.append("one answer produced no card")
        what = ownwords.get("whatText") or ""
        if "It will write about" not in what:
            fails.append(f"the panel does not say what it will write about before "
                         f"spending two real requests: {what!r}")
        if not ownwords.get("pairShown"):
            fails.append("pressing the payoff button showed no pair")
        a, b = ownwords.get("draftA") or "", ownwords.get("draftB") or ""
        if not a or not b:
            fails.append("half the pair is empty -- an empty 'with' draft reads "
                         "as 'your answers made it write nothing'")
        if a == b:
            fails.append("both drafts are identical -- the panel is claiming a "
                         "difference it did not measure")
        if ownwords.get("pairFlexDir") != "column":
            fails.append(f"the drafts are not stacked ({ownwords.get('pairFlexDir')!r}) -- "
                         "side by side invites scanning for changed words, which "
                         "is the dishonest reading")
        if ownwords.get("markCount"):
            fails.append("something in the pair is highlighted -- a highlight "
                         "count is a confident lie about which words came from where")
        if "read them both out loud" not in (ownwords.get("pairNote") or ""):
            fails.append("the pair does not say that nothing is marked up")
        if "Leverage" not in (ownwords.get("cardPassed") or ""):
            fails.append("the demo call was not given the card, so its two drafts "
                         "could not differ by it")
        # THE FAILURE PATH, which never happens by accident and is the one that
        # would otherwise leave a stale pair sitting under an error.
        if not ownwords.get("failPairHidden") or ownwords.get("failDraft"):
            fails.append("a failed press leaves the previous pair on screen -- "
                         "the panel showing evidence it did not just gather")
        if not ownwords.get("failErrShown"):
            fails.append("a failed press says nothing")
        note("In your own words (fourth Profile tab)")

        # THE ONE EXTRA WIZARD STEP — pills, added to the first-run STEPS
        # array. Driven through the real buttons (Onboard.reopen(), #obNext),
        # not by reaching into the wizard's closure, because STEPS/render/at
        # are private to its IIFE and were never meant to be poked directly.
        wiz = json.loads(cdp.js("""(async () => {
          const r = {};
          await Onboard.reopen();
          const clickChoice = (i) => document.querySelectorAll('.obChoices .obChoice')[i].click();
          const next = () => document.getElementById('obNext').click();

          document.getElementById('obInput').value = 'TestBot';
          document.getElementById('obInput').dispatchEvent(new Event('input'));
          next();                 // Q1 name -> Q2
          clickChoice(0); next(); // Q2 who  -> Q3
          clickChoice(0); next(); // Q3 want -> Q4
          next();                 // Q4 thing (blank is valid) -> Q5
          clickChoice(0); next(); // Q5 rope -> Q6
          [...document.querySelectorAll('.obChoices .obChoice')]
            .find(b => b.textContent.includes('Create one for me')).click();
          next();                 // Q6 where -> Q7 (the pill step)

          r.stepLabel   = document.getElementById('obStepLabel').textContent;
          r.question    = document.getElementById('obQuestion').textContent;
          r.pillRows    = document.querySelectorAll('.obPillRow').length;
          r.pillButtons = document.querySelectorAll('.obPillRow .preset').length;
          r.nextEnabledBeforeAnyPick = !document.getElementById('obNext').disabled;
          r.nextLabel   = document.getElementById('obNext').textContent;

          document.querySelectorAll('.obPillRow').forEach(row => row.querySelector('.preset').click());
          r.pressedCount = document.querySelectorAll('.obPillRow .preset[aria-pressed="true"]').length;

          document.getElementById('askPersonality').value = ''; // simulate a genuinely first-time field
          next(); // Finish
          await new Promise(res => setTimeout(res, 150));
          r.sheetClosed  = document.getElementById('onboardSheet').hidden;
          r.personality  = document.getElementById('askPersonality').value;
          return JSON.stringify(r);
        })()""") or "{}")
        if wiz.get("stepLabel") != "Step 7 of 7":
            fails.append(f"the wizard's step label is wrong at the pill step: {wiz.get('stepLabel')!r}")
        if wiz.get("pillRows") != 3:
            fails.append(f"expected 3 pill rows (pace/mood/warmth), got {wiz.get('pillRows')}")
        if wiz.get("pillButtons") != 7:
            fails.append(f"expected 7 pill options total (2+2+3), got {wiz.get('pillButtons')}")
        if not wiz.get("nextEnabledBeforeAnyPick"):
            fails.append("the pill step blocks Next before any pill is pressed -- "
                         "it is supposed to have no wrong answer, including no answer")
        if wiz.get("nextLabel") != "Finish":
            fails.append(f"the last step's button does not say Finish: {wiz.get('nextLabel')!r}")
        if wiz.get("pressedCount") != 3:
            fails.append(f"pressing one pill per row should press 3 total, got {wiz.get('pressedCount')}")
        if not wiz.get("sheetClosed"):
            fails.append("Finish on the pill step does not close the wizard")
        pers = wiz.get("personality") or ""
        if not pers.strip():
            fails.append("finishing the pill step left #askPersonality empty -- "
                         "the one place this feature reaches the model on the "
                         "next turn did not fire")
        if re.search(r"\d+\s*(second|minute)", pers, re.I):
            fails.append(f"a duration leaked into the written personality: {pers!r}")
        note("first-run wizard: the pill step")

        # BECK'S F2 -- COMING BACK TO CHANGE YOUR STYLE HAS TO DO SOMETHING.
        # The section above leaves #askPersonality holding the wizard's own
        # sentences. Reopening setup is the obvious way to change them, and Q7's
        # hint says you can; before this fix the taps were read and silently
        # discarded, because the field was no longer empty.
        #
        # BOTH DIRECTIONS ARE ASSERTED, and the second one is the reason the fix
        # is not simply "always overwrite": a paragraph a PERSON wrote is not
        # ours to replace, and they are told it was kept rather than left to
        # wonder.
        was = wiz.get("personality") or ""
        again = json.loads(cdp.js("""(async () => {
          const r = {}; const notes = () => [...document.querySelectorAll('.note')].map(n => n.textContent).join(' | ');
          const run = async (pick) => {
            await Onboard.reopen();
            const next = () => document.getElementById('obNext').click();
            const clickChoice = (i) => document.querySelectorAll('.obChoices .obChoice')[i].click();
            document.getElementById('obInput').value = 'TestBot';
            document.getElementById('obInput').dispatchEvent(new Event('input'));
            next(); clickChoice(0); next(); clickChoice(0); next(); next();
            clickChoice(0); next();
            [...document.querySelectorAll('.obChoices .obChoice')]
              .find(b => b.textContent.includes('Create one for me')).click();
            next();
            document.querySelectorAll('.obPillRow').forEach(row => {
              const b = row.querySelectorAll('.preset');
              b[Math.min(pick, b.length - 1)].click();
            });
            next();
            await new Promise(res => setTimeout(res, 200));
            return document.getElementById('askPersonality').value;
          };
          const KEPT = 'did not overwrite';
          r.before = document.getElementById('askPersonality').value;
          r.afterOtherPills = await run(1);           // the OTHER option in each row
          // Matched on the sentence itself, not on "a note appeared": EVERY
          // save adds one, so counting notes would pass whatever happened.
          r.saidKeptWhenItDidNot = notes().includes(KEPT);
          document.getElementById('askPersonality').value =
            'Talk to me like a colleague who already knows the project.';
          r.afterTheirOwnWords = await run(0);        // a paragraph a person wrote
          r.saidKept = notes().includes(KEPT);
          return JSON.stringify(r);
        })()""") or "{}")
        if again.get("before", "") != was:
            fails.append("the pill step's own output did not survive to the next "
                         "section -- this check is measuring the wrong thing")
        if again.get("afterOtherPills") == was:
            fails.append("reopening setup and tapping different pills changed "
                         "nothing -- the taps are being read and discarded, which "
                         "is silent and is what Q7's own hint promises against")
        if not (again.get("afterOtherPills") or "").strip():
            fails.append("changing the pills emptied the personality instead of "
                         "rewriting it")
        if again.get("afterTheirOwnWords") != \
                'Talk to me like a colleague who already knows the project.':
            fails.append("three taps overwrote a paragraph the PERSON wrote -- "
                         f"it now reads {again.get('afterTheirOwnWords')!r}")
        if again.get("saidKeptWhenItDidNot"):
            fails.append("the app said it kept the person's wording on a pass "
                         "where it replaced its own -- the message is being said "
                         "when it is not true")
        if not again.get("saidKept"):
            fails.append("their own words were kept and nothing on screen said so "
                         "-- silence is the fault this fix is about")
        note("setup reopened to change the style (F2)")

        print(f"update  : {upcur} / {upnew}")
        print(f"about-me: {aboutme}")
        print(f"sign-in : {signin}")
        print(f"conns   : {conn}")
        print(f"folder  : {f.get('label')!r}  (full path on tooltip: {f.get('title')!r})")
        print(f"idle    : {idle}")
        print(f"pointer : {hover}")
        print(f"talking : {talking}")
        print(f"lit frame, sign-in : {signin_lit:.4%}")
        print(f"lit frame, idle    : {lit:.4%}")
        print(f"lit frame, talking : {talk_lit:.4%}")
        print(f"pointer reaches canvas : {reached}")
    except Exception:
        import traceback
        crash_tb = traceback.format_exc()
    finally:
        proc.terminate()

    if crash_tb:
        print(f"\nCRASHED after section {checked} of the run — everything "
              "numbered above this line actually completed; nothing after it "
              "did, and none of it was checked:")
        print(crash_tb)
        if fails:
            print(f"({len(fails)} assertion(s) had already failed before the crash:)")
            for f in fails:
                print(f"  - {f}")
        return 1

    if fails:
        print("\nFAIL:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"\nOK — {checked} sections checked, ring renders, pointer reaches "
          "it, speech hook is live.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
