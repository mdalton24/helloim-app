/* THE PREVIEW IN THE CORNER OF helloim.ai.
 *
 * REBUILT ROUND 1, 2026-09-06 (Mastermind consensus), REPLACING A LIVE MODEL.
 * The previous version of this file proxied every typed message to
 * Cloudflare Workers AI at the edge -- a real model, called straight from
 * the browser, on the one site whose whole pitch is "the model runs where
 * you tell it to and never on infrastructure you didn't choose." Mark's
 * rule is flat: NO MODEL IS CALLED FROM THE BROWSER. A visitor typing into
 * a corner widget has no way to know it is not the product they are about
 * to buy -- so a live edge model here was the site quietly doing the exact
 * thing it argues against.
 *
 * WHAT THIS IS INSTEAD: canned questions, canned answers, nothing else.
 * Every answer is a short string sitting in the array below, taken
 * verbatim or near-verbatim from this site's own #faq section so nothing
 * here says anything the rest of the page does not already say. There is
 * no text input, on purpose -- a free-text box implies the thing behind it
 * understood what was typed, and nothing here understands anything. Chips
 * only, so there is nothing to misinterpret and nothing to fake.
 *
 * ZERO NETWORK. No fetch, no XHR, no beacon, nothing. That is not merely
 * policy here, it is the whole point being demonstrated: the label below
 * says "no AI model runs on this site" and the only way that label stays
 * true under a click is if the code genuinely never reaches for the
 * network. Open the browser's network panel while using this and the
 * proof is that there is nothing to see.
 *
 * NO FRAMEWORK, NO BUILD STEP. Same house rule as the rest of this site.
 *
 * LEFTOVER, FLAGGED RATHER THAN GUESSED AT: the Worker this site deploys
 * behind (nameos/deploy.py, worker.js -- outside this site/ folder, so
 * out of scope for this edit) still wires an AI binding and an /api/chat
 * route for the old widget to call. Nothing in this file calls that route
 * any more, so it is now dead server-side infrastructure rather than a
 * live model call -- worth removing in a follow-up, but that is a deploy-
 * side change and deploy is explicitly not part of this round.
 */
(function () {
  "use strict";

  /* IT EXCLUDES ITSELF WHERE SOMEBODY IS ALREADY CONVERTING. Same reasoning
     as before: a panel that opens over the form somebody is filling in
     competes with the exact action the page exists for. */
  var EXCLUDE = [/^\/login\/?$/, /^\/signup\/?$/, /^\/account\/?$/,
                 /^\/auth\//, /^\/beta\/?$/];
  var path = location.pathname.replace(/\/index\.html$/, "/");
  for (var i = 0; i < EXCLUDE.length; i++) {
    if (EXCLUDE[i].test(path)) return;
  }

  /* THE SCRIPT. Question shown on the chip, answer shown once it is
     pressed. Kept short — a corner widget, not the FAQ page — and kept
     consistent with #faq on index.html rather than saying it differently
     in two places on the same site. */
  var SCRIPT = [
    { q: "Do I need my own AI account?",
      a: "Not necessarily. Connect your own Claude, OpenAI or Gemini " +
         "account and it runs on that. Prefer to keep everything in-house? " +
         "Point it at a local model on your own machine instead." },
    { q: "Where does my data go?",
      a: "Your folder stays on your machine. Connect a cloud brain and " +
         "what travels is your request plus the files it has to read to " +
         "answer it — to that provider, under your own account. Run a " +
         "local model and nothing leaves your machine at all." },
    { q: "What does it cost?",
      a: "The app is free while it's in early access. Whichever brain you " +
         "connect, you pay that provider directly for your own usage — " +
         "that bill is yours, not ours. A local model has no usage bill." },
    { q: "Can it do things on my computer?",
      a: "Only if you turn that on, one step at a time. It asks before " +
         "every action and waits for you to approve that exact step. " +
         "It never runs on its own." },
    { q: "What's the AI Boardroom?",
      a: "If you've connected more than one brain, it can ask all of them " +
         "the same question, then have your primary brain read every " +
         "answer and write one recommendation — agreements and splits " +
         "both stay visible." },
    { q: "Which computers does it run on?",
      a: "Windows today. The installer brings everything with it — " +
         "nothing else to install first." }
  ];

  var asked = [];  // indexes into SCRIPT already shown, in order

  /* The site's own tokens, hard-coded rather than read from :root, so the
     widget looks right on a page that has not defined them. */
  var css = document.createElement("style");
  css.textContent =
    ".hai-dot{position:fixed;right:20px;bottom:20px;z-index:9998;display:flex;" +
    "align-items:center;gap:9px;padding:12px 18px 12px 15px;border:0;" +
    "border-radius:999px;cursor:pointer;color:#06231A;background:#52FFA5;" +
    "font:600 14px/1 system-ui,-apple-system,Segoe UI,sans-serif;" +
    "box-shadow:0 8px 30px rgba(0,0,0,.5)}" +
    ".hai-dot:hover{background:#6BFDFF}" +
    ".hai-dot:focus-visible{outline:2px solid #6BFDFF;outline-offset:3px}" +
    ".hai-dot svg{width:17px;height:17px;fill:none;stroke:currentColor;" +
    "stroke-width:2;stroke-linecap:round;stroke-linejoin:round}" +
    ".hai-panel{position:fixed;right:20px;bottom:20px;z-index:9999;display:none;" +
    "flex-direction:column;width:min(376px,calc(100vw - 28px));" +
    "height:min(540px,calc(100vh - 40px));border-radius:14px;overflow:hidden;" +
    "background:#12161B;border:1px solid #1E252D;color:#DFE5EC;" +
    "box-shadow:0 24px 64px rgba(0,0,0,.62);" +
    "font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}" +
    ".hai-panel.on{display:flex}" +
    ".hai-head{display:flex;align-items:center;gap:9px;padding:13px 15px;" +
    "border-bottom:1px solid #1E252D}" +
    ".hai-head b{font-size:14px}" +
    ".hai-head span{font-size:12px;color:#7D8894}" +
    ".hai-x{margin-left:auto;background:transparent;border:0;color:#7D8894;" +
    "font-size:21px;line-height:1;cursor:pointer;padding:0 3px}" +
    ".hai-x:hover{color:#DFE5EC}" +
    ".hai-log{flex:1 1 auto;overflow-y:auto;padding:14px 15px;display:flex;" +
    "flex-direction:column;gap:9px;scrollbar-width:thin;" +
    "scrollbar-color:#1E252D transparent}" +
    ".hai-m{padding:10px 13px;border-radius:12px;font-size:14px;max-width:88%;" +
    "background:#0B0D10;align-self:flex-start;white-space:pre-wrap;" +
    "overflow-wrap:anywhere}" +
    ".hai-me{align-self:flex-end;background:rgba(82,255,165,.13);color:#DFE5EC}" +
    /* CHIPS, not a text box — see the file header for why there is no
       input here. Same button visual language as the rest of the site
       (.btn.ghost), scaled down for a 376px panel. */
    ".hai-chips{display:flex;flex-direction:column;gap:7px;padding:11px 15px;" +
    "border-top:1px solid #1E252D}" +
    ".hai-chip{font:inherit;font-size:13px;text-align:left;padding:9px 12px;" +
    "border-radius:9px;border:1px solid #1E252D;color:#DFE5EC;" +
    "background:#0B0D10;cursor:pointer}" +
    ".hai-chip:hover{border-color:#52FFA5;color:#52FFA5}" +
    ".hai-chip:focus-visible{outline:2px solid #6BFDFF;outline-offset:2px}" +
    ".hai-done{margin:0;padding:2px 2px 0;font-size:13px;color:#7D8894}" +
    ".hai-done a{color:#52FFA5}" +
    ".hai-foot{margin:0;padding:8px 15px 11px;font-size:11px;color:#7D8894;" +
    "border-top:1px solid #1E252D}" +
    "@media (max-width:520px){.hai-panel{right:10px;bottom:10px}" +
    ".hai-dot{right:12px;bottom:12px}}" +
    "@media (prefers-reduced-motion:reduce){.hai-dot,.hai-panel{transition:none}}";
  document.head.appendChild(css);

  var dot = document.createElement("button");
  dot.className = "hai-dot";
  dot.type = "button";
  dot.setAttribute("aria-label", "Try a scripted preview of helloim.ai");
  dot.innerHTML =
    "<svg viewBox='0 0 24 24' aria-hidden='true'>" +
    "<path d='M21 12a9 9 0 1 1-3.2-6.9'/><path d='M8 11h8M8 15h5'/></svg>" +
    "<span>Try it</span>";

  var panel = document.createElement("div");
  panel.className = "hai-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Scripted preview of helloim.ai");
  panel.innerHTML =
    "<div class='hai-head'><b>helloim.ai</b><span>a few real questions</span>" +
    "<button class='hai-x' type='button' aria-label='Close'>&times;</button></div>" +
    "<div class='hai-log'></div>" +
    "<div class='hai-chips'></div>" +
    /* SAID BEFORE THEY ASK, not when caught, same reasoning the old widget
       used for its own disclosure — and the exact wording the task asked
       for, so nobody has to infer what "scripted" means here. */
    "<p class='hai-foot'>Scripted preview — no AI model runs on this site.</p>";

  document.body.appendChild(dot);
  document.body.appendChild(panel);

  var log = panel.querySelector(".hai-log");
  var chipsBox = panel.querySelector(".hai-chips");
  var lastFocus = null;

  function line(text, mine) {
    var el = document.createElement("div");
    el.className = "hai-m" + (mine ? " hai-me" : "");
    el.textContent = text;
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  function renderChips() {
    chipsBox.innerHTML = "";
    var remaining = SCRIPT.filter(function (_, idx) { return asked.indexOf(idx) === -1; });
    if (!remaining.length) {
      /* AN EMPTY STYLED BOX IS A BUG, NOT AN ENDING — so once every chip is
         used the slot gets real content instead of just vanishing. */
      var done = document.createElement("p");
      done.className = "hai-done";
      done.innerHTML = "That's everything in this preview. The " +
        "<a href=\"#faq\">FAQ</a> below has more, or " +
        "<a href=\"#get\">get access</a> to ask the real thing.";
      chipsBox.appendChild(done);
      return;
    }
    remaining.forEach(function (item) {
      var idx = SCRIPT.indexOf(item);
      var b = document.createElement("button");
      b.type = "button";
      b.className = "hai-chip";
      b.textContent = item.q;
      b.addEventListener("click", function () { ask(idx); });
      chipsBox.appendChild(b);
    });
  }

  function ask(idx) {
    if (asked.indexOf(idx) !== -1) return;
    asked.push(idx);
    line(SCRIPT[idx].q, true);
    line(SCRIPT[idx].a, false);
    renderChips();
  }

  function open(on) {
    panel.classList.toggle("on", on);
    dot.style.display = on ? "none" : "";
    if (on) {
      lastFocus = document.activeElement;
      if (!log.children.length) {
        line("Hey — pick a question. Every answer here is written ahead " +
             "of time, nothing is generated live.");
        renderChips();
      }
      var firstChip = chipsBox.querySelector(".hai-chip");
      if (firstChip) firstChip.focus();
    } else if (lastFocus && lastFocus.focus) {
      lastFocus.focus();
    }
  }

  dot.addEventListener("click", function () { open(true); });
  panel.querySelector(".hai-x").addEventListener("click", function () { open(false); });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && panel.classList.contains("on")) open(false);
  });
})();
