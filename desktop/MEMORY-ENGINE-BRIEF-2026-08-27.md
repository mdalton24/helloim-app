# Memory Engine brief — pasted by Mark, 2026-08-27 00:4x

Kept verbatim in REQUESTS.md. This file is the working notes on top of it.

## The two constraints that shape it, neither of which is in the brief

### 1. There is exactly one channel into the model

NameOS does not host a model. It shells out to Claude Code. So everything a
memory engine retrieves has to reach the model through one of three doors and
there is no fourth:

- `--append-system-prompt` — ours, on every turn, already used for the voice.
- the working folder's `CLAUDE.md` — already used by the About-you profile.
- an MCP server we run and hand over with `--mcp-config`.

**A retrieval engine that cannot get its results into the prompt is a database
with a UI on it.** The design has to start from the door, not from the store.

The MCP route is the interesting one: it makes memory a TOOL the model can
query when it decides it needs to, rather than a blob we paste in whether it is
relevant or not. That also answers the brief's own worry about token bloat far
better than slicing does.

### 2. `sqlite-vec` is the thing he told me not to do

The brief names it. It is a native binary extension that has to be compiled and
loaded per platform — exactly the class of dependency Mark ruled out on
2026-08-26: *"We should only be using things native to windows before resorting
to other items to force things to happen."* That rule already cost a bundled
Node runtime and a subscription connector.

**What is already in the box:**

- **SQLite with FTS5** — BM25 ranking, built in, no extension, and `rusqlite`
  is a pure-Rust dependency that compiles for Windows with nothing installed.
- **Embeddings from the local model** — ollama is already on this machine and
  already serves models. Vectors can be produced without a service, and cosine
  similarity over a few thousand rows is a loop, not a library.

That is hybrid retrieval — BM25 plus vectors — with nothing installed on the
user's machine. **Put this to him before building on it**, because it is a
deliberate departure from what his brief specifies.

## Scope, said plainly

Storage layer, async extraction worker, retrieval interface, per-agent scoping,
a Memory Hub UI and a test suite is a multi-session build. Saying otherwise is
the fastest route to a half version that looks finished.

Suggested order, each one shippable on its own:

1. **The bridge (Tier 2) first.** It is the smallest piece and the one with the
   most obvious value — "never start over" is the whole promise. It also needs
   no embeddings, no vector search and no UI.
2. Storage + FTS5 + the retrieval interface.
3. The MCP memory server, so the model can ask rather than be told.
4. ~~Extraction worker~~ — **KILLED 2026-08-27, not deferred.** Approved by
   Jarvis, carried to Mark by Jarvis. The full rationale is in the module doc
   of `src-tauri/src/facts.rs` ("Slice 4 — the extraction worker — was
   KILLED"); short form: every model call goes through the CUSTOMER'S Claude
   Code sign-in, so a background pass is a silent recurring charge on someone
   else's bill; an async extractor is an invisible writer and would make
   memory poisoning LESS visible than slice 3's in-turn saves; and mechanical
   extraction of semantic facts is junk by construction. Replaced by 4a
   (`memory::GUIDANCE` in the system prompt), 4b (the bridge's
   promote-to-memory line) and 4c (`facts::memory_stats` — the measurement,
   with the reopen threshold written in its doc comment). Do not re-propose
   the worker without reading that module doc and the 4c numbers first.
5. The Memory Hub UI — inspect, edit, forget, export. **Carries a security
   job**: review-and-removal of assistant-written lines is the recovery path
   for a poisoned memory (see the residual-risk note in facts.rs), and 4c's
   `memory_stats` is ready for it to surface.
