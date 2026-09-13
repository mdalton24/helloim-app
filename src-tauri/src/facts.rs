//! Memory — Tier 3, the things it learns about you and keeps.
//!
//! The memory-engine brief, 2026-08-27; slice 2 of five. Tier 2 (the
//! session bridge, `memory.rs`) answers "where were we"; this answers "what do
//! you already know about me" — the preferences, constraints and decisions
//! that should not have to be said twice.
//!
//! ## The shape: THE MARKDOWN IS THE STORE. THE DATABASE IS ITS INDEX.
//!
//! `.nameos/memory/facts.md`, inside the folder the customer chose, is the
//! authoritative record. Its own text says "Delete a line here and it is
//! forgotten" — and the code means it. SQLite (`memory.db` beside it) is a
//! rebuildable search index over that file: FTS5 for BM25 ranking, plus the
//! metadata a text file carries badly (verified flags, timestamps).
//!
//! How the two stay honest with each other:
//! - Every write lands in the database and is mirrored to the markdown, and a
//!   `meta` table stores the SHA-256 of the markdown WE last wrote.
//! - Every `open()` hashes the current file. Hash == stamp means nobody
//!   touched it by hand; if the mirror is missing a row the database holds
//!   (a mirror write that failed mid-sequence), the FILE is rewritten — never
//!   the database. Hash != stamp means a HAND EDIT, and the file wins: lines
//!   gone from the file are deleted from the database (FTS rows included, via
//!   the content-table triggers), lines added by hand become new unverified
//!   facts, and a reworded line is delete-old-plus-add-new.
//! - A missing database rebuilds itself from the markdown on the next open.
//!   A missing markdown is rewritten from the database — deleting the FILE is
//!   recoverable; deleting a LINE is a choice, and only the second is
//!   "forget". Forgetting is line-granular, on purpose.
//!
//! The stamp is a HASH, not an mtime, for one specific reason: if the mirror
//! write fails after a database commit, the file still matches the old stamp,
//! so the reconciler knows the file is merely STALE rather than hand-edited —
//! and must never delete the fact the database legitimately holds.
//!
//! This also makes "cancel and it is still yours" true by construction rather
//! than by an export feature: the store IS the plain-text file already in the
//! customer's folder. `export_memory` additionally hands everything back as
//! JSON for machines.
//!
//! ## Why there are NO EMBEDDINGS here — read this before re-proposing them
//!
//! The brief said "embeddings from the local model". That premise described
//! the DEVELOPMENT machine, not the product: ollama listens on loopback on
//! the box this was written on, and a customer's Windows machine has no
//! ollama — NameOS ships no model by design. Anthropic's API has no
//! embeddings endpoint either (their docs recommend Voyage AI: a second
//! third-party key plus a network round trip per retrieval — rejected). At
//! this corpus size, BM25 + recency + verified-first carries retrieval. If
//! quality measurably fails later, the door is `ort` — already shipped in
//! this binary for TTS — running a small ONNX embedding model on the CPU,
//! and the column is one additive `ALTER TABLE` away. Do not open that door
//! on a hunch; open it on a failing retrieval benchmark.
//!
//! ## Concurrency — the cross-process lock is SQLite itself
//!
//! Slice 3 put a SECOND PROCESS on this store: the MCP memory server Claude
//! Code spawns (`mcp.rs`). Two layers keep that safe:
//!
//! - WAL journal mode and a 5-second busy timeout, set on every open, so a
//!   reader never blocks behind a writer.
//! - Every reconcile-or-mutate sequence that touches the mirror runs inside
//!   `BEGIN IMMEDIATE` (`with_write_txn`). SQLite's writer lock is
//!   cross-process by design and — unlike an O_EXCL lock file — cannot go
//!   stale, because it dies with the process. The mirror write and the stamp
//!   sit INSIDE the transaction, so no two processes can interleave "write
//!   facts.md" and "stamp its hash"; the interleaving that would read as a
//!   hand edit and delete facts is structurally impossible. Proven by an
//!   integration test that runs two real server processes against one store.
//!   `STORE_LOCK` remains as the cheap in-process layer (Tauri commands run
//!   on a thread pool).
//!
//! ## The residual risk this store carries — read before building the Hub
//!
//! The MCP server lets the MODEL write memories. An attacker who can inject
//! text into the model's context — a web page it reads, a file in the folder,
//! an email body — cannot erase anything (there is no forget tool, see
//! `mcp.rs`), but CAN plant a durable false memory that replays into every
//! future session. Erasure is loud and recoverable; POISONING IS SILENT AND
//! PERMANENT unless it is visible. The mitigations here: every model-written
//! fact carries `source = "the assistant"`, forced server-side and rendered
//! in facts.md where the customer can see it at a glance, and it arrives
//! unverified, so a ranker and a reader can prefer human facts. What is NOT
//! built yet: review and removal in the product. SLICE 5'S HUB IS THEREFORE
//! CARRYING A SECURITY JOB, not just a convenience one — inspect-and-forget
//! of assistant-written lines is the recovery path for a poisoned memory,
//! and whoever designs that panel needs to know it before they design it.
//!
//! ## Slice 4 — the extraction worker — was KILLED, not deferred
//!
//! The brief specifies an async extraction pipeline: a separate model pass
//! that reads the conversation and writes facts. It was killed on 2026-08-27,
//! deliberately, and anyone re-reading the brief and re-proposing it needs
//! these three reasons in front of them first:
//!
//! 1. **It is a silent recurring charge on the CUSTOMER'S account.** NameOS
//!    ships no model and no API key; every call goes through the customer's
//!    own Claude Code sign-in. A background extraction pass per session is
//!    not "an extra turn" — it is metered spend on someone else's bill, for a
//!    feature they never see run, discovered by a customer reading their
//!    invoice. There is no free inference on a customer's machine (the same
//!    premise error the embeddings note above already caught once).
//! 2. **It is a purpose-built silent-write channel.** An in-turn
//!    `memory_save` is a visible tool call — the customer watches it happen
//!    in the conversation. An async extractor reads the same
//!    attacker-influenceable text (fetched pages, files in the folder) and
//!    writes with no trace in the conversation the customer saw. Provenance
//!    forcing would survive; "who can watch the write happen" would not. It
//!    would make the exact attack slice 3 mitigated LESS visible.
//! 3. **Mechanical extraction cannot do it either.** Match the mechanism to
//!    the content: session facts (files touched, exit codes) are facts on
//!    disk, so the Tier 2 bridge is mechanical and right. "Prefers short
//!    replies" is a judgement, and a regex-grade extractor writing judgements
//!    into a PERMANENT store produces confident junk. A sparse memory is
//!    recoverable — the customer says it again and the model saves it then; a
//!    polluted one erodes trust in every retrieval that follows.
//!
//! What replaced it: 4a (memory guidance in `--append-system-prompt`, see
//! `memory::GUIDANCE`), 4b (the bridge's promote-to-memory line,
//! `memory::bridge_prompt`), and 4c (`memory_stats` below — the measurement
//! that decides whether this question ever gets reopened, and on what number).
//!
//! FTS5 arrives inside `rusqlite`'s `bundled` SQLite — no extension, no DLL,
//! nothing installed on the customer's machine. Verified by the tests below
//! on Linux; the Windows binary links (cross-compiled from here) but no
//! Windows box has run these tests — documented-not-tested.

use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::Mutex;

/// Long enough to be a real fact, short enough that nobody pastes a document
/// into their own memory by accident. Public because the MCP tool layer
/// names the limit in its rejection message.
pub const MAX_FACT: usize = 600;

/// The provenance the MCP server forces onto every model-written fact, and
/// the string `memory_stats` counts by. ONE constant on purpose: if the
/// writer and the measurement each had their own copy, a rewording would
/// silently zero the metric while the writes carried on.
pub const ASSISTANT_SOURCE: &str = "the assistant";

/// Serialises reconcile → mutate → mirror within this process. Tauri runs
/// commands on a thread pool; without this, two concurrent writes can
/// interleave "write facts.md" and "stamp its hash" so the stamp describes
/// one version and the file another — and the next open would misread that
/// as a hand edit and reconcile against it, deleting a fact nobody deleted.
static STORE_LOCK: Mutex<()> = Mutex::new(());

fn lock() -> std::sync::MutexGuard<'static, ()> {
    // A poisoned lock means another thread panicked mid-write; the store
    // heals from either side on the next reconcile, so keep serving.
    STORE_LOCK.lock().unwrap_or_else(|e| e.into_inner())
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Fact {
    #[serde(default)]
    pub id: i64,
    /// "preference" | "project" | "decision" | "fact" — the brief's own four.
    /// A string rather than an enum so a file written by a later version stays
    /// readable by an earlier one.
    pub kind: String,
    /// The thing itself, in plain words.
    pub text: String,
    /// Which specialist this belongs to, or empty for everyone. The brief calls
    /// this the agent scope; empty is the global user context.
    #[serde(default)]
    pub scope: String,
    /// Where it came from, shown next to anything retrieved. The brief asks for
    /// source attribution and this is it.
    #[serde(default)]
    pub source: String,
    #[serde(default)]
    pub at: i64,
    /// Confirmed by a person. `remember` always stores false — a caller
    /// (including a model behind the slice-3 MCP server) must not certify its
    /// own memories. The only door to true is `edit_fact`, which is a human
    /// action in the Hub.
    #[serde(default)]
    pub verified: bool,
}

fn now() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn mem_dir(workdir: &str) -> Option<PathBuf> {
    let p = Path::new(workdir.trim());
    if workdir.trim().is_empty() || !p.is_dir() {
        return None;
    }
    Some(p.join(".nameos").join("memory"))
}

/// Open the store: ensure the folder and schema, set WAL + busy timeout for
/// the second process slice 3 will add, then reconcile the index against the
/// markdown (the truth). Every public entry point goes through here, so a
/// hand edit is honoured before any read or write acts on stale state.
///
/// Error strings deliberately never contain the user's folder path — they
/// surface in the UI and in logs, and a path is a disclosure.
pub fn open(workdir: &str) -> Result<Connection, String> {
    let d = mem_dir(workdir).ok_or_else(|| "No working folder for memory.".to_string())?;
    std::fs::create_dir_all(&d).map_err(|e| format!("could not create the memory folder: {e}"))?;
    let conn = Connection::open(d.join("memory.db"))
        .map_err(|e| format!("could not open the memory index: {e}"))?;
    conn.busy_timeout(std::time::Duration::from_secs(5))
        .map_err(|e| e.to_string())?;
    // WAL so slice 3's MCP server process can read while the app writes.
    //
    // FOUND BY THE TWO-PROCESS TEST, not by reasoning: converting a database
    // INTO WAL takes an exclusive lock on a path that does NOT consult the
    // busy handler, so two processes opening a brand-new store at the same
    // moment collided with an instant "database is locked" — the 5s timeout
    // never ran. Steady state was never the problem; creation was. So: read
    // the mode first, convert only when needed, and retry the conversion by
    // hand. Same treatment for the schema batch, which writes on first
    // creation.
    retry_busy(|| {
        let mode: String = conn.query_row("PRAGMA journal_mode", [], |r| r.get(0))?;
        if mode.eq_ignore_ascii_case("wal") {
            return Ok(());
        }
        conn.query_row("PRAGMA journal_mode=WAL", [], |r| r.get::<_, String>(0))
            .map(|_| ())
    })
    .map_err(|e| e.to_string())?;
    // The schema in one place, run every open. Cheap, and it means a deleted
    // database heals itself rather than needing a migration step nobody runs.
    retry_busy(|| conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS facts(
             id INTEGER PRIMARY KEY,
             kind TEXT NOT NULL,
             text TEXT NOT NULL,
             scope TEXT NOT NULL DEFAULT '',
             source TEXT NOT NULL DEFAULT '',
             at INTEGER NOT NULL,
             verified INTEGER NOT NULL DEFAULT 0
         );
         CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts
             USING fts5(text, content='facts', content_rowid='id');
         -- The index follows the table automatically. Without these an edit
         -- leaves the search index describing a fact that no longer says that.
         CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
             INSERT INTO facts_fts(rowid, text) VALUES (new.id, new.text);
         END;
         CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
             INSERT INTO facts_fts(facts_fts, rowid, text) VALUES('delete', old.id, old.text);
         END;
         CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
             INSERT INTO facts_fts(facts_fts, rowid, text) VALUES('delete', old.id, old.text);
             INSERT INTO facts_fts(rowid, text) VALUES (new.id, new.text);
         END;
         -- One row that matters: 'md_sha256', the hash of the markdown WE
         -- last wrote. It lives in the database on purpose: delete the
         -- database and the stamp goes with it, which is exactly the state
         -- that makes the next open rebuild the index from the file.
         CREATE TABLE IF NOT EXISTS meta(
             key TEXT PRIMARY KEY,
             value TEXT NOT NULL
         );",
    ))
    .map_err(|e| e.to_string())?;
    reconcile(&conn, &d)?;
    Ok(conn)
}

/// Retry a statement that can fail with SQLITE_BUSY / SQLITE_LOCKED on paths
/// where SQLite does not consult the busy handler (journal-mode conversion,
/// first-creation DDL races). Bounded at roughly the same five seconds as the
/// busy timeout, then the real error surfaces.
fn retry_busy<T>(mut f: impl FnMut() -> rusqlite::Result<T>) -> rusqlite::Result<T> {
    let mut waited_ms = 0u64;
    loop {
        match f() {
            Err(rusqlite::Error::SqliteFailure(e, msg))
                if matches!(
                    e.code,
                    rusqlite::ErrorCode::DatabaseBusy | rusqlite::ErrorCode::DatabaseLocked
                ) =>
            {
                if waited_ms >= 5_000 {
                    return Err(rusqlite::Error::SqliteFailure(e, msg));
                }
                std::thread::sleep(std::time::Duration::from_millis(50));
                waited_ms += 50;
            }
            other => return other,
        }
    }
}

fn md_hash(text: &str) -> String {
    Sha256::digest(text.as_bytes())
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

fn stamp(conn: &Connection) -> Option<String> {
    conn.query_row("SELECT value FROM meta WHERE key = 'md_sha256'", [], |r| r.get(0))
        .ok()
}

fn set_stamp(conn: &Connection, h: &str) -> Result<(), String> {
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES('md_sha256', ?1)",
        params![h],
    )
    .map_err(|e| e.to_string())
    .map(|_| ())
}

/// Run a mutate-plus-mirror sequence under SQLite's own writer lock.
///
/// THIS IS THE CROSS-PROCESS LOCK. `BEGIN IMMEDIATE` takes the database's
/// writer lock, which reaches every process on the file and dies with the
/// process that holds it — no stale-lockfile failure mode. The mirror write
/// and the stamp happen INSIDE the transaction, so a second writer (another
/// thread, or the MCP server process) blocks on BEGIN until file and stamp
/// have landed together; the stamp-describes-one-version-file-another
/// interleaving cannot occur. On failure everything rolls back as one —
/// facts and stamp together — so the next reconcile sees a coherent pair and
/// converges without deleting a legitimate row.
fn with_write_txn<T>(
    conn: &Connection,
    f: impl FnOnce(&Connection) -> Result<T, String>,
) -> Result<T, String> {
    // Belt to the busy-timeout's braces: BEGIN IMMEDIATE does use the busy
    // handler, but the same open-time races that bypass it (see open()) can
    // surface here on a store's very first transactions.
    retry_busy(|| conn.execute_batch("BEGIN IMMEDIATE")).map_err(|e| e.to_string())?;
    match f(conn) {
        Ok(v) => {
            conn.execute_batch("COMMIT").map_err(|e| e.to_string())?;
            Ok(v)
        }
        Err(e) => {
            let _ = conn.execute_batch("ROLLBACK");
            Err(e)
        }
    }
}

/// The canonical text of the store. What this renders IS the memory; the
/// database is derived from it.
fn render_markdown(facts: &[Fact]) -> String {
    let mut s = String::from("# What it knows\n\n");
    s.push_str(
        "Written by helloim.ai. This file is yours: plain text, in your folder, safe to\n\
         edit or delete. Delete a line here and it is forgotten. If the whole file\n\
         goes missing it is rewritten from the app's index, memory intact.\n\n",
    );
    for kind in ["preference", "project", "decision", "fact"] {
        let mine: Vec<&Fact> = facts.iter().filter(|f| f.kind == kind).collect();
        if mine.is_empty() {
            continue;
        }
        s.push_str(&format!("## {}\n\n", match kind {
            "preference" => "Preferences",
            "project" => "Projects",
            "decision" => "Decisions",
            _ => "Facts",
        }));
        for f in mine {
            s.push_str(&format!("- {}", f.text));
            if !f.scope.trim().is_empty() {
                s.push_str(&format!(" _(scope: {})_", f.scope.trim()));
            }
            if !f.source.trim().is_empty() {
                s.push_str(&format!(" _(from {})_", f.source.trim()));
            }
            s.push('\n');
        }
        s.push('\n');
    }
    s
}

/// Mirror the database to the markdown, then stamp the exact bytes written.
///
/// ORDER MATTERS AND IS LOAD-BEARING: file first, stamp second. If the write
/// fails, the stamp still matches the previous file, so the next reconcile
/// sees "stale mirror" (rewrite the file) rather than "hand edit" (start
/// deleting facts). Swapping these two lines reintroduces the data-loss race
/// this module was rebuilt to remove.
fn write_markdown(conn: &Connection, dir: &Path, facts: &[Fact]) -> Result<(), String> {
    let s = render_markdown(facts);
    std::fs::write(dir.join("facts.md"), &s)
        .map_err(|e| format!("could not write the memory file: {e}"))?;
    set_stamp(conn, &md_hash(&s))
}

/// A fact as parsed back out of the customer's own file.
struct Line {
    kind: String,
    text: String,
    scope: String,
    source: String,
}

/// Strip a trailing `_(<opener>…)_` annotation, returning (text, annotation).
fn take_annotation(text: &str, opener: &str) -> (String, String) {
    if text.ends_with(")_") {
        if let Some(i) = text.rfind(opener) {
            let inner = &text[i + opener.len()..text.len() - 2];
            return (text[..i].trim_end().to_string(), inner.trim().to_string());
        }
    }
    (text.trim_end().to_string(), String::new())
}

/// Read facts back out of the markdown. Deliberately forgiving: section
/// headings map to kinds (anything unrecognised is a plain "fact"), bullets
/// are facts, everything else — prose, blank lines, a stray comment — is
/// ignored rather than treated as an error. It is the customer's file and a
/// mangled edit must degrade to "some lines were not understood", never to a
/// refusal to load their memory.
fn parse_markdown(content: &str) -> Vec<Line> {
    let mut out = Vec::new();
    let mut kind = "fact".to_string();
    let mut seen: HashSet<(String, String)> = HashSet::new();
    for raw in content.lines() {
        let line = raw.trim();
        if let Some(h) = line.strip_prefix("## ") {
            kind = match h.trim() {
                "Preferences" => "preference",
                "Projects" => "project",
                "Decisions" => "decision",
                _ => "fact",
            }
            .to_string();
            continue;
        }
        let Some(rest) = line.strip_prefix("- ") else { continue };
        let (rest, source) = take_annotation(rest, " _(from ");
        let (text, scope) = take_annotation(&rest, " _(scope: ");
        let text: String = text.trim().chars().take(MAX_FACT).collect();
        if text.is_empty() {
            continue;
        }
        let key = (scope.clone(), text.to_lowercase());
        // A duplicated line is one fact — same rule as remember().
        if seen.insert(key) {
            out.push(Line { kind: kind.clone(), text, scope, source });
        }
    }
    out
}

/// The markdown is the truth; make the database agree with it.
///
/// Cases, in the order they are checked:
/// - File missing: rewritten from the database (if it ever existed — a fresh
///   folder stays empty until the first remember). Deleting the whole file is
///   ambiguous — accident, cleanup, sync hiccup — so it is a lost copy, not
///   "forget everything". Forgetting is line-granular.
/// - Hash matches the stamp: no hand edit. One further check heals a STALE
///   mirror forward — a database that is ahead of the file (failed mirror
///   write) rewrites the file. The database row was legitimately written and
///   must never be lost to a stale mirror.
/// - Hash differs (or there is no stamp: a rebuilt database, a legacy
///   install, a hand-authored file): the file wins. Deletions, additions,
///   then a normalised rewrite and a fresh stamp.
fn reconcile(conn: &Connection, dir: &Path) -> Result<(), String> {
    // Fast path outside any transaction: most opens find nothing to do, and
    // taking the writer lock for a read would serialise every reader in
    // every process behind every other.
    if !reconcile_needed(conn, dir)? {
        return Ok(());
    }
    with_write_txn(conn, |c| {
        // Re-check INSIDE the lock: another process may have been mid-write
        // when we peeked (its file already on disk, its stamp not yet
        // committed), or may have finished this exact reconcile while we
        // waited on BEGIN. Classic check-then-act; the recheck closes it.
        if !reconcile_needed(c, dir)? {
            return Ok(());
        }
        reconcile_now(c, dir)
    })
}

/// Read-only peek: is there any divergence between file, stamp and index?
fn reconcile_needed(conn: &Connection, dir: &Path) -> Result<bool, String> {
    let stamped = stamp(conn);
    match std::fs::read_to_string(dir.join("facts.md")) {
        // File gone: work to do only if it ever existed.
        Err(_) => Ok(stamped.is_some()),
        Ok(c) => {
            let h = md_hash(&c);
            if stamped.as_deref() != Some(h.as_str()) {
                return Ok(true); // hand edit, rebuild, or legacy install
            }
            // Stamp matches: the only remaining divergence is a stale mirror
            // (database ahead of a file whose write failed).
            let all = all_facts(conn)?;
            Ok(md_hash(&render_markdown(&all)) != h)
        }
    }
}

/// The full pass. Only ever runs inside `with_write_txn`.
fn reconcile_now(conn: &Connection, dir: &Path) -> Result<(), String> {
    let path = dir.join("facts.md");
    let stamped = stamp(conn);
    let content = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => {
            if stamped.is_some() {
                let all = all_facts(conn)?;
                write_markdown(conn, dir, &all)?;
            }
            return Ok(());
        }
    };
    let h = md_hash(&content);
    if stamped.as_deref() == Some(h.as_str()) {
        let all = all_facts(conn)?;
        let fresh = render_markdown(&all);
        if md_hash(&fresh) != h {
            std::fs::write(&path, &fresh)
                .map_err(|e| format!("could not write the memory file: {e}"))?;
            set_stamp(conn, &md_hash(&fresh))?;
        }
        return Ok(());
    }

    let parsed = parse_markdown(&content);
    let existing = all_facts(conn)?;

    let mut want: HashSet<(String, String)> = HashSet::new();
    for p in &parsed {
        want.insert((p.scope.clone(), p.text.to_lowercase()));
    }

    // Deletions — with one act of mercy: a line that lost its scope
    // annotation still claims its scoped row by text alone. Legacy mirrors
    // predate the annotation entirely, and people delete what they do not
    // recognise; an upgrade or a tidy-up must never silently forget a
    // specialist's memory.
    for f in &existing {
        let t = f.text.to_lowercase();
        let kept = want.contains(&(f.scope.clone(), t.clone()))
            || want.contains(&(String::new(), t));
        if !kept {
            conn.execute("DELETE FROM facts WHERE id = ?1", params![f.id])
                .map_err(|e| e.to_string())?;
        }
    }

    // Additions: lines the database does not hold become new unverified
    // facts. The mirror image of the mercy rule above: a scopeless line whose
    // text already exists under some scope is that fact, not a new global one.
    let mut have: HashMap<String, HashSet<String>> = HashMap::new();
    for f in &existing {
        have.entry(f.text.to_lowercase()).or_default().insert(f.scope.clone());
    }
    for p in &parsed {
        let t = p.text.to_lowercase();
        let already = match have.get(&t) {
            Some(scopes) => {
                scopes.contains(&p.scope) || (p.scope.is_empty() && !scopes.is_empty())
            }
            None => false,
        };
        if !already {
            conn.execute(
                "INSERT INTO facts(kind, text, scope, source, at, verified)
                 VALUES(?1, ?2, ?3, ?4, ?5, 0)",
                params![p.kind, p.text, p.scope, p.source, now()],
            )
            .map_err(|e| e.to_string())?;
        }
    }

    // Normalise the file and stamp it, so the next open is a hash compare
    // and nothing more.
    let all = all_facts(conn)?;
    write_markdown(conn, dir, &all)
}

/// Store one fact.
///
/// Who may call: the app's own webview, and (via slice 3) the MCP memory
/// server acting for the model. What a wrong caller gets: nothing exploitable
/// — `verified` is FORCED false here regardless of what was sent, so no
/// caller can certify its own memory; the only door to true is `edit_fact`.
/// Malformed input: empty text is refused with a plain error; oversized text
/// is truncated to MAX_FACT; a duplicate (same text, same scope, case-
/// insensitive) updates the existing row rather than creating a second one.
/// Errors name the operation, never the customer's folder path.
#[tauri::command]
pub fn remember(workdir: String, mut fact: Fact) -> Result<Fact, String> {
    let _g = lock();
    let text = fact.text.trim();
    if text.is_empty() {
        return Err("Nothing to remember.".into());
    }
    fact.text = text.chars().take(MAX_FACT).collect();
    if fact.kind.trim().is_empty() {
        fact.kind = "fact".into();
    }
    fact.at = now();
    fact.verified = false;

    let conn = open(&workdir)?;
    let d = mem_dir(&workdir).ok_or_else(|| "No working folder for memory.".to_string())?;
    with_write_txn(&conn, move |c| {
        // THE SAME THING TWICE IS ONE THING. Without this, a preference stated
        // in three sessions becomes three rows and outvotes everything else in
        // every search it appears in.
        let existing: Option<i64> = c
            .query_row(
                "SELECT id FROM facts WHERE lower(text) = lower(?1) AND scope = ?2",
                params![fact.text, fact.scope],
                |r| r.get(0),
            )
            .ok();
        if let Some(id) = existing {
            c.execute(
                "UPDATE facts SET at = ?1, kind = ?2, source = ?3 WHERE id = ?4",
                params![fact.at, fact.kind, fact.source, id],
            )
            .map_err(|e| e.to_string())?;
            fact.id = id;
        } else {
            c.execute(
                "INSERT INTO facts(kind, text, scope, source, at, verified)
                 VALUES(?1, ?2, ?3, ?4, ?5, 0)",
                params![fact.kind, fact.text, fact.scope, fact.source, fact.at],
            )
            .map_err(|e| e.to_string())?;
            fact.id = c.last_insert_rowid();
        }
        let all = all_facts(c)?;
        write_markdown(c, &d, &all)?;
        Ok(fact)
    })
}

fn row(r: &rusqlite::Row) -> rusqlite::Result<Fact> {
    Ok(Fact {
        id: r.get(0)?,
        kind: r.get(1)?,
        text: r.get(2)?,
        scope: r.get(3)?,
        source: r.get(4)?,
        at: r.get(5)?,
        verified: r.get::<_, i32>(6)? != 0,
    })
}

fn all_facts(conn: &Connection) -> Result<Vec<Fact>, String> {
    let mut st = conn
        .prepare("SELECT id,kind,text,scope,source,at,verified FROM facts ORDER BY at DESC")
        .map_err(|e| e.to_string())?;
    let out = st
        .query_map([], row)
        .map_err(|e| e.to_string())?
        .filter_map(Result::ok)
        .collect();
    Ok(out)
}

/// Everything, for the Hub (slice 5). This is the OWNER'S view and crosses
/// scopes on purpose; the model-facing retrieval path is `search`, which does
/// not. Forgiving on error (an empty list, not a crash) because its consumer
/// is a listing panel.
#[tauri::command]
pub fn list_facts(workdir: String) -> Vec<Fact> {
    let _g = lock();
    open(&workdir).ok().and_then(|c| all_facts(&c).ok()).unwrap_or_default()
}

/// Forget one fact — from the database, the search index (via the content-
/// table triggers) and the customer-readable file, in one motion. Wrong id:
/// a no-op, not an error, because "already forgotten" and "forgotten" are the
/// same outcome. Errors never name the folder path.
#[tauri::command]
pub fn forget(workdir: String, id: i64) -> Result<(), String> {
    let _g = lock();
    let conn = open(&workdir)?;
    let d = mem_dir(&workdir).ok_or_else(|| "No working folder for memory.".to_string())?;
    with_write_txn(&conn, |c| {
        c.execute("DELETE FROM facts WHERE id = ?1", params![id])
            .map_err(|e| e.to_string())?;
        let all = all_facts(c)?;
        write_markdown(c, &d, &all)
    })
}

/// Edit a fact's text and set its verified flag. This is the ONLY writer of
/// `verified = true`, and it is wired to a human action in the Hub — a model
/// cannot reach it through the retrieval interface. Empty text is refused
/// with a pointer at delete instead.
#[tauri::command]
pub fn edit_fact(workdir: String, id: i64, text: String, verified: bool) -> Result<(), String> {
    let _g = lock();
    let t = text.trim();
    if t.is_empty() {
        return Err("A memory cannot be empty — delete it instead.".into());
    }
    let conn = open(&workdir)?;
    let d = mem_dir(&workdir).ok_or_else(|| "No working folder for memory.".to_string())?;
    with_write_txn(&conn, |c| {
        c.execute(
            "UPDATE facts SET text = ?1, verified = ?2 WHERE id = ?3",
            params![t.chars().take(MAX_FACT).collect::<String>(), verified as i32, id],
        )
        .map_err(|e| e.to_string())?;
        let all = all_facts(c)?;
        write_markdown(c, &d, &all)
    })
}

/// Turn a person's sentence into something FTS5 will accept.
///
/// FTS5's query language treats plenty of ordinary punctuation as syntax, so a
/// raw question mark or apostrophe is a parse error rather than a search. Each
/// word becomes its own quoted term; anything that is not a word disappears.
fn to_match(query: &str) -> String {
    let terms: Vec<String> = query
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| w.len() > 2)
        .take(12)
        .map(|w| format!("\"{}\"", w.to_lowercase()))
        .collect();
    terms.join(" OR ")
}

/// The retrieval interface — the function slice 3's MCP server sits on. A
/// plain library call, no Tauri state, so a second process can reach it by
/// opening the same store.
///
/// The contract, spelled out because this is the trust boundary:
/// - Who may call: anything holding a connection from `open()` — the app's
///   commands here, the MCP server next slice.
/// - Scope is enforced HERE, not by the caller: a row comes back only if it
///   is global or belongs to exactly the scope named. The scope string is a
///   bound parameter, so a hostile value ("code' OR '1'='1") is an inert
///   literal that matches nothing — it can never widen the query to a third
///   specialist's rows.
/// - Malformed query: FTS syntax is stripped by `to_match`; a query with no
///   searchable words returns Ok(empty), because "nothing to search for" is
///   an answer, not a failure.
/// - Errors are Err, distinct from Ok(empty): "the store is unavailable" must
///   never read as "you have no memories" to a model deciding what it knows.
///   Error strings never contain the customer's folder path.
/// - Nothing here can write, and nothing here can set `verified`.
pub fn search(
    conn: &Connection,
    query: &str,
    scope: &str,
    limit: i64,
) -> Result<Vec<Fact>, String> {
    let m = to_match(query);
    if m.is_empty() {
        return Ok(Vec::new());
    }
    let sql = "SELECT f.id,f.kind,f.text,f.scope,f.source,f.at,f.verified
               FROM facts_fts JOIN facts f ON f.id = facts_fts.rowid
               WHERE facts_fts MATCH ?1 AND (f.scope = '' OR f.scope = ?2)
               ORDER BY bm25(facts_fts) ASC, f.verified DESC, f.at DESC
               LIMIT ?3";
    let mut st = conn.prepare(sql).map_err(|e| e.to_string())?;
    let rows = st
        .query_map(params![m, scope, limit], row)
        .map_err(|e| e.to_string())?
        .filter_map(Result::ok)
        .collect();
    Ok(rows)
}

/// The brief's single query interface, as the webview sees it. Thin wrapper
/// over `search` — same contract, plus the limit clamp. Returns Err when the
/// store cannot be opened, which the caller must show as "memory unavailable",
/// never as an empty result.
#[tauri::command]
pub fn retrieve_relevant_memory(
    workdir: String,
    query: String,
    agent_role: String,
    limit: Option<u32>,
) -> Result<Vec<Fact>, String> {
    let _g = lock();
    let limit = limit.unwrap_or(5).clamp(1, 25) as i64;
    let conn = open(&workdir)?;
    search(&conn, &query, &agent_role, limit)
}

/// Everything, as one JSON document — the machine-readable half of "cancel
/// and it is still yours". The human-readable half is `facts.md` itself,
/// which IS the store rather than a copy of it.
#[tauri::command]
pub fn export_memory(workdir: String) -> Result<String, String> {
    let _g = lock();
    let conn = open(&workdir)?;
    let all = all_facts(&conn)?;
    serde_json::to_string_pretty(&all).map_err(|e| e.to_string())
}

/// Slice 4c — the measurement that stands where the extraction worker would
/// have been (see the kill rationale in the module doc above).
///
/// "The model won't save enough on its own" is a HYPOTHESIS, and this is how
/// it gets tested instead of assumed. Same discipline as the embeddings door
/// above: named, closed, openable on a failing measurement rather than a
/// hunch.
///
/// **The number that would justify reopening extraction:** `assistantCount`
/// still ZERO after two weeks of real sessions in a folder (the bridge file's
/// mtime shows sessions are happening) means the 4a guidance is not firing —
/// revisit the OPT-IN, USER-VISIBLE end-of-session save design, with this
/// number in hand. A small-but-nonzero trickle is the design working; do not
/// build an extractor because the count is merely modest.
///
/// The contract: callable by the app's own webview (the Hub surfaces it in
/// slice 5); a bad or missing folder is a plain Err naming the operation and
/// never the path; the reply carries counts and timestamps only — no fact
/// text, so nothing here can leak a memory into a log line.
#[tauri::command]
pub fn memory_stats(workdir: String) -> Result<serde_json::Value, String> {
    let _g = lock();
    let conn = open(&workdir)?;
    let all = all_facts(&conn)?;
    let assistant: Vec<&Fact> = all.iter().filter(|f| f.source == ASSISTANT_SOURCE).collect();
    Ok(serde_json::json!({
        "totalCount": all.len(),
        "assistantCount": assistant.len(),
        // 0 means "never", and the field is still present so a caller can
        // tell "never" from "could not read".
        "newestAssistantAt": assistant.iter().map(|f| f.at).max().unwrap_or(0),
        "verifiedCount": all.iter().filter(|f| f.verified).count(),
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp(n: &str) -> PathBuf {
        let p = std::env::temp_dir().join(format!("nameos-facts-{}-{}", n, std::process::id()));
        let _ = std::fs::remove_dir_all(&p);
        std::fs::create_dir_all(&p).unwrap();
        p
    }
    fn f(kind: &str, text: &str, scope: &str) -> Fact {
        Fact { id: 0, kind: kind.into(), text: text.into(), scope: scope.into(),
               source: "said in conversation".into(), at: 0, verified: false }
    }
    fn md_path(d: &Path) -> PathBuf {
        d.join(".nameos/memory/facts.md")
    }
    fn db_path(d: &Path) -> PathBuf {
        d.join(".nameos/memory/memory.db")
    }

    #[test]
    fn it_remembers_and_finds_by_words() {
        let d = tmp("find"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("preference", "the user prefers short replies with no preamble", "")).unwrap();
        remember(wd.clone(), f("project", "The pricing page ships on Friday", "")).unwrap();

        let hits = retrieve_relevant_memory(wd.clone(), "how should you write replies?".into(), "".into(), Some(5)).unwrap();
        assert!(!hits.is_empty(), "found nothing");
        assert!(hits[0].text.contains("short replies"), "wrong hit: {:?}", hits[0].text);
        let _ = std::fs::remove_dir_all(&d);
    }

    /// The brief asks for isolation between specialists. A creative agent must
    /// not be handed the code agent's environment notes.
    #[test]
    fn a_specialist_never_sees_another_specialists_memory() {
        let d = tmp("scope"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("fact", "The staging database lives on port 5433", "code")).unwrap();
        remember(wd.clone(), f("preference", "Headlines are sentence case, never title case", "creative")).unwrap();
        remember(wd.clone(), f("fact", "the user is in Texas", "")).unwrap();

        let creative = retrieve_relevant_memory(wd.clone(), "database port headlines Texas".into(), "creative".into(), Some(10)).unwrap();
        let texts: Vec<&str> = creative.iter().map(|x| x.text.as_str()).collect();
        assert!(texts.iter().any(|t| t.contains("sentence case")), "missing its own: {texts:?}");
        assert!(texts.iter().any(|t| t.contains("Texas")), "missing global: {texts:?}");
        assert!(!texts.iter().any(|t| t.contains("5433")), "leaked another scope: {texts:?}");
        let _ = std::fs::remove_dir_all(&d);
    }

    /// Scope is enforced by a bound parameter, so an injection-shaped scope
    /// string is an inert literal. It must neither widen the query into a
    /// third specialist's rows nor break anything.
    #[test]
    fn a_hostile_scope_string_stays_inside_its_scope() {
        let d = tmp("hostile"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("fact", "The staging database lives on port 5433", "code")).unwrap();
        remember(wd.clone(), f("fact", "the user is in Texas", "")).unwrap();

        for evil in ["code' OR '1'='1", "code\" OR \"\"=\"", "' OR scope LIKE '%", "*"] {
            let hits = retrieve_relevant_memory(
                wd.clone(), "staging database port Texas".into(), evil.to_string(), Some(10),
            ).unwrap();
            assert!(
                !hits.iter().any(|h| h.text.contains("5433")),
                "scope {evil:?} leaked a scoped row: {hits:?}"
            );
        }
        let _ = std::fs::remove_dir_all(&d);
    }

    /// Slice 4c: the measurement counts exactly the assistant's writes — the
    /// same string mcp.rs forces — and nothing a human wrote. An empty store
    /// answers zeros, distinct from an unreachable one, which errors.
    #[test]
    fn memory_stats_counts_assistant_writes_and_only_those() {
        let d = tmp("stats"); let wd = d.to_string_lossy().to_string();

        let empty = memory_stats(wd.clone()).unwrap();
        assert_eq!(empty["assistantCount"], 0);
        assert_eq!(empty["totalCount"], 0);
        assert_eq!(empty["newestAssistantAt"], 0, "never must read as 0, not null");

        remember(wd.clone(), f("preference", "the user prefers short replies", "")).unwrap();
        let mut model_written = f("fact", "The staging server is called dax", "");
        model_written.source = ASSISTANT_SOURCE.into();
        remember(wd.clone(), model_written).unwrap();

        let s = memory_stats(wd.clone()).unwrap();
        assert_eq!(s["totalCount"], 2);
        assert_eq!(s["assistantCount"], 1, "human-sourced fact was counted");
        assert!(s["newestAssistantAt"].as_i64().unwrap() > 0);
        // No fact text in the reply — counts only, so nothing can leak a
        // memory into whatever log line carries this.
        assert!(!s.to_string().contains("dax"), "stats leaked fact text: {s}");

        assert!(memory_stats("/definitely/not/here".into()).is_err(),
            "an unreachable store must be an error, never zeros");
        let _ = std::fs::remove_dir_all(&d);
    }

    /// Saying the same thing twice must not create two rows, or a repeated
    /// preference outvotes everything else in every search it appears in.
    #[test]
    fn the_same_fact_twice_is_one_fact() {
        let d = tmp("dupe"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("preference", "No emoji in anything", "")).unwrap();
        remember(wd.clone(), f("preference", "no EMOJI in anything", "")).unwrap();
        assert_eq!(list_facts(wd.clone()).len(), 1);
        let _ = std::fs::remove_dir_all(&d);
    }

    /// A caller cannot certify its own memory: remember() forces verified to
    /// false no matter what arrives on the wire. The only door to true is
    /// edit_fact, a human action.
    #[test]
    fn a_caller_cannot_verify_its_own_memory() {
        let d = tmp("verify"); let wd = d.to_string_lossy().to_string();
        let mut fact = f("fact", "I am definitely trustworthy", "");
        fact.verified = true;
        let stored = remember(wd.clone(), fact).unwrap();
        assert!(!stored.verified, "remember() let a caller certify itself");
        assert!(!list_facts(wd.clone())[0].verified);

        edit_fact(wd.clone(), stored.id, "I am definitely trustworthy".into(), true).unwrap();
        assert!(list_facts(wd.clone())[0].verified, "the human door must still work");
        let _ = std::fs::remove_dir_all(&d);
    }

    /// "Forget this" has to actually forget it -- from the database AND from
    /// the file the person can read.
    #[test]
    fn forgetting_removes_it_from_both_places() {
        let d = tmp("forget"); let wd = d.to_string_lossy().to_string();
        let kept = remember(wd.clone(), f("fact", "Keep this one", "")).unwrap();
        let gone = remember(wd.clone(), f("fact", "Forget the secret handshake", "")).unwrap();

        forget(wd.clone(), gone.id).unwrap();
        let left = list_facts(wd.clone());
        assert_eq!(left.len(), 1);
        assert_eq!(left[0].id, kept.id);

        let md = std::fs::read_to_string(md_path(&d)).unwrap();
        assert!(!md.contains("secret handshake"), "still in the file a person reads");
        assert!(md.contains("Keep this one"));

        // And it is gone from search, not merely hidden from the list.
        let hits = retrieve_relevant_memory(wd.clone(), "secret handshake".into(), "".into(), Some(5)).unwrap();
        assert!(hits.is_empty(), "search still returns it: {hits:?}");
        let _ = std::fs::remove_dir_all(&d);
    }

    /// THE PROMISE THE FILE MAKES IN ITS OWN TEXT: delete a line here and it
    /// is forgotten. From the list, from the database, and from the search
    /// index — a hand edit is not a suggestion.
    #[test]
    fn a_hand_deleted_line_is_forgotten_everywhere() {
        let d = tmp("handdel"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("preference", "the user prefers short replies", "")).unwrap();
        remember(wd.clone(), f("preference", "No emoji in anything", "")).unwrap();

        let md = std::fs::read_to_string(md_path(&d)).unwrap();
        let edited: String = md.lines().filter(|l| !l.contains("No emoji")).collect::<Vec<_>>().join("\n");
        std::fs::write(md_path(&d), edited).unwrap();

        let left = list_facts(wd.clone());
        assert_eq!(left.len(), 1, "hand-deleted line survived: {left:?}");
        assert!(left[0].text.contains("short replies"));

        let hits = retrieve_relevant_memory(wd.clone(), "emoji".into(), "".into(), Some(5)).unwrap();
        assert!(hits.is_empty(), "forgotten line still answers searches: {hits:?}");

        // The mirror is rewritten normalised, so the file agrees with itself.
        let md2 = std::fs::read_to_string(md_path(&d)).unwrap();
        assert!(!md2.contains("No emoji"));
        let _ = std::fs::remove_dir_all(&d);
    }

    /// The other half of the file being editable: a line the customer writes
    /// by hand becomes a real, retrievable, UNVERIFIED fact.
    #[test]
    fn a_hand_added_line_is_remembered() {
        let d = tmp("handadd"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("fact", "the user is in Texas", "")).unwrap();

        let mut md = std::fs::read_to_string(md_path(&d)).unwrap();
        md.push_str("- The office is closed on Fridays\n");
        std::fs::write(md_path(&d), md).unwrap();

        let hits = retrieve_relevant_memory(wd.clone(), "closed on Fridays".into(), "".into(), Some(5)).unwrap();
        assert!(!hits.is_empty(), "hand-added line is not retrievable");
        assert!(hits[0].text.contains("closed on Fridays"));
        assert!(!hits[0].verified, "a hand-added line must arrive unverified");
        assert_eq!(hits[0].kind, "fact");
        let _ = std::fs::remove_dir_all(&d);
    }

    /// A reworded line is delete-old-plus-add-new — and the OLD text must
    /// leave the search index, not just the table. A stale FTS row surviving
    /// its fact is exactly the bug the content-table triggers exist to
    /// prevent and exactly the one nobody checks for.
    #[test]
    fn a_reworded_line_leaves_no_trace_of_the_old_one() {
        let d = tmp("reword"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("fact", "The deploy password lives in the vault", "")).unwrap();

        let md = std::fs::read_to_string(md_path(&d)).unwrap();
        let edited = md.replace(
            "The deploy password lives in the vault",
            "Deploy credentials live in the vault",
        );
        std::fs::write(md_path(&d), edited).unwrap();

        let old = retrieve_relevant_memory(wd.clone(), "password".into(), "".into(), Some(5)).unwrap();
        assert!(old.is_empty(), "old wording still in the search index: {old:?}");
        let new = retrieve_relevant_memory(wd.clone(), "credentials vault".into(), "".into(), Some(5)).unwrap();
        assert_eq!(new.len(), 1, "new wording not retrievable");
        assert_eq!(list_facts(wd.clone()).len(), 1, "reword produced a duplicate");
        let _ = std::fs::remove_dir_all(&d);
    }

    /// The database is an index. Delete it and the markdown rebuilds it —
    /// kinds, sources and scopes intact. (The verified flag lives only in the
    /// index and honestly does not survive; a rebuilt memory is unverified.)
    #[test]
    fn the_database_rebuilds_from_the_markdown() {
        let d = tmp("rebuild"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("preference", "Short replies only", "")).unwrap();
        remember(wd.clone(), f("decision", "We ship on Fridays", "")).unwrap();
        remember(wd.clone(), f("fact", "The staging database lives on port 5433", "code")).unwrap();

        for suffix in ["", "-wal", "-shm"] {
            let _ = std::fs::remove_file(d.join(format!(".nameos/memory/memory.db{suffix}")));
        }

        let back = list_facts(wd.clone());
        assert_eq!(back.len(), 3, "rebuild lost facts: {back:?}");
        assert!(back.iter().any(|x| x.kind == "preference" && x.text.contains("Short replies")));
        assert!(back.iter().any(|x| x.kind == "decision" && x.text.contains("Fridays")));
        assert!(back.iter().any(|x| x.scope == "code" && x.text.contains("5433")),
            "scope did not survive the rebuild: {back:?}");
        assert!(back.iter().all(|x| x.source == "said in conversation"), "source lost: {back:?}");

        let hits = retrieve_relevant_memory(wd.clone(), "staging port".into(), "code".into(), Some(5)).unwrap();
        assert!(!hits.is_empty(), "rebuilt index does not answer searches");
        let _ = std::fs::remove_dir_all(&d);
    }

    /// An untouched file is left byte-identical alone, and database-only
    /// state (the verified flag, ids) survives the no-op.
    #[test]
    fn an_untouched_file_is_left_alone() {
        let d = tmp("noop"); let wd = d.to_string_lossy().to_string();
        let a = remember(wd.clone(), f("fact", "Keep me exactly as I am", "")).unwrap();
        edit_fact(wd.clone(), a.id, "Keep me exactly as I am".into(), true).unwrap();

        let before = std::fs::read_to_string(md_path(&d)).unwrap();
        let listed = list_facts(wd.clone());
        let after = std::fs::read_to_string(md_path(&d)).unwrap();

        assert_eq!(before, after, "a no-op open rewrote the customer's file");
        assert_eq!(listed.len(), 1);
        assert_eq!(listed[0].id, a.id, "a no-op open churned row ids");
        assert!(listed[0].verified, "a no-op open dropped the verified flag");
        let _ = std::fs::remove_dir_all(&d);
    }

    /// THE REASON THE STAMP IS A HASH AND NOT AN MTIME. A mirror write that
    /// failed leaves the file stale but matching the old stamp; the
    /// reconciler must read that as "stale copy — heal it forward", never as
    /// "hand edit — delete the fact the database legitimately holds".
    #[test]
    fn a_stale_mirror_never_deletes_facts() {
        let d = tmp("stale"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("fact", "Fact number one", "")).unwrap();
        let v1 = std::fs::read_to_string(md_path(&d)).unwrap();
        remember(wd.clone(), f("fact", "Fact number two", "")).unwrap();

        // Reproduce the exact post-failure state: file back at v1, stamp
        // matching v1 — as if the second mirror write never happened.
        std::fs::write(md_path(&d), &v1).unwrap();
        let db = Connection::open(db_path(&d)).unwrap();
        db.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('md_sha256', ?1)",
            params![md_hash(&v1)],
        )
        .unwrap();
        drop(db);

        let all = list_facts(wd.clone());
        assert_eq!(all.len(), 2, "a stale mirror deleted a legitimate fact: {all:?}");

        // And the mirror healed forward: the file now carries both facts.
        let healed = std::fs::read_to_string(md_path(&d)).unwrap();
        assert!(healed.contains("Fact number two"), "stale mirror was not healed");
        let _ = std::fs::remove_dir_all(&d);
    }

    /// Upgrade path: mirrors written before the scope annotation existed (and
    /// hand edits that drop it) still claim their scoped rows by text. An
    /// upgrade must never silently forget a specialist's memory or duplicate
    /// it into the global scope.
    #[test]
    fn scoped_facts_survive_a_legacy_mirror() {
        let d = tmp("legacy"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("preference", "Headlines are sentence case", "creative")).unwrap();

        let md = std::fs::read_to_string(md_path(&d)).unwrap();
        let legacy = md.replace(" _(scope: creative)_", "");
        std::fs::write(md_path(&d), legacy).unwrap();
        // A legacy database has no stamp at all.
        let db = Connection::open(db_path(&d)).unwrap();
        db.execute("DELETE FROM meta", []).unwrap();
        drop(db);

        let all = list_facts(wd.clone());
        assert_eq!(all.len(), 1, "legacy mirror duplicated or dropped the fact: {all:?}");
        assert_eq!(all[0].scope, "creative", "the upgrade lost the scope");
        let _ = std::fs::remove_dir_all(&d);
    }

    /// Ranking on a realistic corpus: ~30 rows where the newest rows are weak
    /// single-term matches and the right answer is the oldest row. Naive
    /// recency gets this wrong; BM25 must not.
    #[test]
    fn the_right_row_wins_over_recency() {
        let d = tmp("rank"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("decision", "The invoice footer is dark green with the logo on the left", "")).unwrap();
        remember(wd.clone(), f("fact", "Green is one of the brand colors", "")).unwrap();
        for i in 0..28 {
            remember(wd.clone(), f("fact", &format!("Meeting note {i}: the color discussion continues"), "")).unwrap();
        }

        let hits = retrieve_relevant_memory(
            wd.clone(), "what color is the invoice footer?".into(), "".into(), Some(5),
        ).unwrap();
        assert!(!hits.is_empty(), "found nothing in a 30-row corpus");
        assert!(
            hits[0].text.contains("invoice footer"),
            "recency outvoted relevance: {:?}",
            hits.iter().map(|h| h.text.as_str()).collect::<Vec<_>>()
        );
        let _ = std::fs::remove_dir_all(&d);
    }

    /// Two writers at once: WAL, the busy timeout and the store lock together
    /// must produce twenty facts and zero errors, never a SQLITE_BUSY or a
    /// mangled mirror.
    #[test]
    fn two_writers_do_not_lose_or_mangle_anything() {
        let d = tmp("threads"); let wd = d.to_string_lossy().to_string();
        let (wa, wb) = (wd.clone(), wd.clone());
        let t1 = std::thread::spawn(move || {
            for i in 0..10 {
                remember(wa.clone(), f("fact", &format!("thread one fact number {i}"), "")).unwrap();
            }
        });
        let t2 = std::thread::spawn(move || {
            for i in 0..10 {
                remember(wb.clone(), f("fact", &format!("thread two fact number {i}"), "")).unwrap();
            }
        });
        t1.join().unwrap();
        t2.join().unwrap();

        assert_eq!(list_facts(wd.clone()).len(), 20);
        let md = std::fs::read_to_string(md_path(&d)).unwrap();
        assert_eq!(md.matches("thread one fact").count(), 10, "mirror lost writes");
        assert_eq!(md.matches("thread two fact").count(), 10, "mirror lost writes");
        let _ = std::fs::remove_dir_all(&d);
    }

    /// A question typed by a person contains punctuation FTS5 treats as syntax.
    /// Before this was handled, an ordinary question was a parse error.
    #[test]
    fn a_real_question_does_not_break_the_query() {
        let d = tmp("punct"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("preference", "the user hates long emails", "")).unwrap();
        for q in ["what's the deal with emails?", "emails -- long ones?", "\"emails\"", "AND OR NOT"] {
            let _ = retrieve_relevant_memory(wd.clone(), q.into(), "".into(), Some(5));
        }
        let hits = retrieve_relevant_memory(wd.clone(), "what's the deal with emails?".into(), "".into(), Some(5)).unwrap();
        assert!(!hits.is_empty(), "a normal question found nothing");
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn the_folder_is_readable_without_us() {
        let d = tmp("md"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("preference", "Sentence case headlines", "")).unwrap();
        let md = std::fs::read_to_string(md_path(&d)).unwrap();
        assert!(md.contains("# What it knows"));
        assert!(md.contains("Sentence case headlines"));
        // Wraps across a line in the file, so match the half that carries
        // the meaning rather than a phrase that spans the break.
        assert!(md.contains("edit or delete"), "the permission to change it is missing");
        assert!(md.contains("forgotten"), "the promise the code now keeps is missing");
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn export_gives_everything_back() {
        let d = tmp("export"); let wd = d.to_string_lossy().to_string();
        remember(wd.clone(), f("fact", "One", "")).unwrap();
        remember(wd.clone(), f("fact", "Two", "")).unwrap();
        let js = export_memory(wd.clone()).unwrap();
        let back: Vec<Fact> = serde_json::from_str(&js).unwrap();
        assert_eq!(back.len(), 2);
        let _ = std::fs::remove_dir_all(&d);
    }

    /// A missing folder is an ERROR on the paths a model will consume, not a
    /// silence. "The store is unavailable" must never read as "you have no
    /// memories".
    #[test]
    fn a_missing_folder_is_an_error_not_a_silence() {
        assert!(list_facts("/definitely/not/here".into()).is_empty());
        assert!(
            retrieve_relevant_memory("/nope".into(), "x".into(), "".into(), None).is_err(),
            "store-unavailable collapsed into an empty result"
        );
        assert!(remember("/nope".into(), f("fact", "x", "")).is_err());
        assert!(export_memory("/nope".into()).is_err());
    }

    /// Error strings surface in the UI and in logs. They name the operation,
    /// never the customer's folder path.
    #[test]
    fn errors_never_name_the_users_folder() {
        let d = tmp("leak"); let wd = d.to_string_lossy().to_string();
        // A file squatting on the .nameos name makes create_dir_all fail.
        std::fs::write(d.join(".nameos"), "not a folder").unwrap();

        let err = remember(wd.clone(), f("fact", "x", "")).unwrap_err();
        assert!(!err.contains(&wd), "error leaks the folder path: {err}");
        assert!(!err.contains("nameos-facts-leak"), "error leaks the folder name: {err}");

        let err2 = retrieve_relevant_memory(wd.clone(), "query words".into(), "".into(), None).unwrap_err();
        assert!(!err2.contains(&wd), "error leaks the folder path: {err2}");
        let _ = std::fs::remove_dir_all(&d);
    }
}
