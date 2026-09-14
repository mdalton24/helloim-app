//! Startup — what this app does when it cannot draw a window.
//!
//! **THE FAULT THIS EXISTS FOR, FOUND BY RUNNING THE BINARY ON 2026-08-28 AND
//! NOT BY READING IT.** On a machine whose GPU the webview cannot use, NameOS
//! launched, stayed alive, and mapped no window at all. No dialog, nothing on
//! stdout, nothing anywhere on disk. From outside it is indistinguishable from
//! a crash, from a corrupt download, and from a machine that is simply slow —
//! and there is nothing for the person to screenshot, because the failure's
//! entire visible form is an empty desktop.
//!
//! **MEASURED HERE, and it is worse than "it prints an error nobody sees".**
//! Run with no display reachable at all, the process dies inside `tao`'s GTK
//! init with a **panic**, not an `Err`:
//!
//! ```text
//! thread 'main' panicked at tao-0.35.3/src/platform_impl/linux/event_loop.rs:217
//! Failed to initialize gtk backend!
//! ```
//!
//! That matters for the shape of the fix. `main` ends in
//! `.run(...).expect("failed to start the window")`, and it is reasonable to
//! assume the `expect` is what fires — so a `match` on the `Result` looks like
//! the whole answer. It is not: **`run()` never returns in that case.** The
//! panic hook is the load-bearing part and the `Result` arm is the second net.
//!
//! **AND ON WINDOWS NOTHING PRINTS EVEN WHEN SOMETHING IS PRINTED.** `main.rs`
//! carries `windows_subsystem = "windows"` for every release build, which is
//! correct — nobody wants a console behind their app — and it means a release
//! binary has no stderr at all. Every `eprintln!` in this crate, the default
//! panic message, and that `expect` string all go to a closed handle. **A
//! Windows customer gets exactly nothing.**
//!
//! The likeliest Windows cause is a missing, broken or policy-blocked WebView2
//! Runtime, which is why `preflight` asks about it BEFORE a window is
//! attempted: the failure is then a sentence a person can act on rather than an
//! absence they have to interpret.
//!
//! **WHAT IS DELIBERATELY NOT HERE: forcing software rendering.** The three
//! environment variables that made the app appear on the failing Linux box
//! (`WEBKIT_DISABLE_COMPOSITING_MODE`, `WEBKIT_DISABLE_DMABUF_RENDERER`,
//! `LIBGL_ALWAYS_SOFTWARE`) would also make it slow on every healthy machine.
//! Trading a silent failure for a universal slowdown is not a fix; it is the
//! same bug with better manners. This module makes the failure SAY something.

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};

/// The bundle identifier, duplicated from `tauri.conf.json` ON PURPOSE.
///
/// The log path has to be resolvable before Tauri exists — that is the whole
/// point of this module, since the failure being logged is Tauri failing to
/// start — so `app.path().app_log_dir()` is not available at the moment it is
/// needed. A duplicated constant is the cost, and `the_identifier_matches_the_
/// config` below is the thing that stops it becoming a lie: it reads
/// `tauri.conf.json` at test time and fails if the two ever drift.
///
/// The installer holds a third copy for the same reason and says so
/// (`!define IDENT` in `installer/NameOS.nsi`).
pub const IDENTIFIER: &str = "ai.nameos.desktop";

/// Where the log lives, matching `PathResolver::app_log_dir()` exactly.
///
/// Matching is not tidiness. On Windows this resolves under
/// `%LOCALAPPDATA%\ai.nameos.desktop\`, which is the tree the uninstaller
/// already removes wholesale — so this file cannot become the next "something
/// the uninstaller left behind", which is a scar this product already carries
/// twice over (a loose NameOS.exe on the desktop, and 39.8 MB of EBWebView).
///
/// Read off tauri 2.11.5's own source rather than from documentation:
/// macOS `~/Library/Logs/<id>`, everywhere else `<data_local>/<id>/logs`.
fn log_dir() -> Option<PathBuf> {
    #[cfg(target_os = "macos")]
    {
        let home = std::env::var_os("HOME")?;
        Some(PathBuf::from(home).join("Library/Logs").join(IDENTIFIER))
    }
    #[cfg(target_os = "windows")]
    {
        let local = std::env::var_os("LOCALAPPDATA")?;
        Some(PathBuf::from(local).join(IDENTIFIER).join("logs"))
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let base = std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .filter(|p| p.is_absolute())
            .or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".local/share")))?;
        Some(base.join(IDENTIFIER).join("logs"))
    }
}

fn log_file() -> Option<PathBuf> {
    Some(log_dir()?.join("startup.log"))
}

/// Longest the log may get before the previous one is rolled aside. Two
/// launches' worth of lines is a few hundred bytes; this is room for thousands
/// and still small enough that nobody's disk notices.
const MAX_LOG: u64 = 128 * 1024;

/// Seconds since the epoch, as a UTC date a person can read.
///
/// Hand-rolled rather than pulling in a date crate for one line per launch.
/// The days-to-civil-date conversion is the standard one and it is proven
/// against known dates in the tests below, because a timestamp that is quietly
/// wrong is worse than an epoch count that is obviously raw.
fn utc_stamp(secs: u64) -> String {
    let days = (secs / 86_400) as i64;
    let tod = secs % 86_400;
    // Shift the epoch to 0000-03-01 so leap days land at the end of the cycle.
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    format!(
        "{y:04}-{m:02}-{d:02} {:02}:{:02}:{:02}Z",
        tod / 3600,
        (tod % 3600) / 60,
        tod % 60
    )
}

fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Longest a single log line may be after redaction. Every message this crate
/// actually writes today is a short sentence — a version, a resolved path, a
/// panic location — so this is headroom, not a working limit; it exists so a
/// FUTURE `note(&format!(...))` that accidentally interpolates something big
/// (a whole error body, a prompt) degrades to a truncated line instead of a
/// startup log that quietly becomes a copy of whatever was passed in. Same
/// order of magnitude as `ERROR_BODY_CAP` in the three native-engine wires
/// (500) and `generic_status_error`'s own cap (also 500) in providers.rs — a
/// little larger because a startup line legitimately carries a full path.
const LOG_LINE_CAP: usize = 800;

/// Strip anything shaped like a bearer token or an API key out of a message
/// before it reaches a log line.
///
/// **THE COMMENT ON `note()` BELOW SAID "NEVER A CREDENTIAL" AND NOTHING
/// CHECKED IT — closed 2026-09-03, in the hardening pass the user asked for.**
/// Every `note(...)` call site in this crate was read for this pass — there
/// are two, `main.rs`'s one startup line and this file's own panic/webview
/// diagnostics — and none of them currently pass one, so this is NOT a fix
/// for a live leak. It is the same move `redact_and_truncate` already made
/// for provider error text in `providers.rs`, applied to the one surface that
/// couldn't use that function as-is: `note()` takes a bare string with no
/// provider or key in scope, so there is nothing to match exactly against.
/// This redacts by SHAPE instead — the `Bearer <token>` form every wired
/// provider sends (`provider_env` in providers.rs) and the `sk-` key-prefix
/// OpenAI, OpenRouter and Anthropic's own console keys all share — so a
/// future call site that slips a token into a format string is caught at the
/// boundary rather than depending on the next person reading this doc
/// comment before they write theirs.
///
/// **NOT A CLAIM OF COMPLETENESS.** A key with no recognisable prefix, or one
/// embedded with no surrounding whitespace, can still slip through — the same
/// honesty `redact_and_truncate`'s own tests carry ("some servers echo...
/// this simulates one doing exactly that"), not a promise this catches every
/// shape a secret could take. It catches the shapes this app's own wire
/// format actually produces.
fn redact_secret_shapes(msg: &str) -> String {
    let mut out: Vec<String> = Vec::new();
    let mut redact_next = false;
    for word in msg.split(' ') {
        if redact_next {
            redact_next = false;
            // An empty split segment (double space in the source) is not a
            // token to redact — leave it alone so ordinary spacing survives.
            out.push(if word.is_empty() { String::new() } else { "[redacted]".to_string() });
            continue;
        }
        if word.eq_ignore_ascii_case("bearer") {
            out.push("Bearer".to_string());
            redact_next = true;
            continue;
        }
        if looks_like_an_api_key(word) {
            out.push("[redacted]".to_string());
            continue;
        }
        out.push(word.to_string());
    }
    out.join(" ")
}

/// A word-shaped guess, not a parser. Trims the punctuation a key is commonly
/// wrapped in (a trailing comma, a quote from JSON) before judging it, and
/// requires both the `sk-` prefix AND a length past what any ordinary English
/// word starting `sk-` would reach — the same 8-byte-floor reasoning
/// `redact_and_truncate` uses for the same purpose, sized up because a real
/// key is dozens of characters, not eight.
fn looks_like_an_api_key(word: &str) -> bool {
    let trimmed = word.trim_matches(|c: char| matches!(c, '"' | '\'' | ',' | ';' | ')' | '('));
    trimmed.len() >= 16
        && trimmed.starts_with("sk-")
        && trimmed.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
}

/// The one place a message is made safe to log: shape-redacted, then capped.
/// Truncation reuses `providers::redact_and_truncate`'s char-boundary-safe cut
/// rather than a second `String::truncate` — the release reviewer already found and fixed the
/// panic-on-a-multibyte-boundary version of that bug once; there is no reason
/// to give this file its own copy to rediscover it in.
fn redact_and_cap(msg: &str) -> String {
    crate::providers::redact_and_truncate(redact_secret_shapes(msg), "", LOG_LINE_CAP)
}

/// Write one line to the startup log, and to stderr where there is one.
///
/// **NEVER FAILS AND NEVER PANICS.** Every error is swallowed deliberately: a
/// diagnostic that can itself break the launch is worse than no diagnostic, and
/// the one thing this file must not do is become a new reason the app does not
/// start. If the directory cannot be made or the file cannot be opened, the
/// line is still printed to stderr and the app carries on.
///
/// **WHAT MAY GO IN A LINE.** Our own wording, versions, and error strings
/// handed to us by the platform. **Never a credential, never file content,
/// never the user's working folder** — that path can name a client, and this is
/// a file people paste into support threads. Platform error strings are the
/// accepted edge: they occasionally carry a path of the platform's own choosing
/// and we cannot parse them, so that is stated rather than pretended away.
/// **As of 2026-09-03 that rule is also enforced, not just stated** — see
/// `redact_and_cap` above.
pub fn note(msg: &str) {
    let msg = redact_and_cap(msg);
    let msg = msg.as_str();
    let line = format!("{} {}\n", utc_stamp(now_secs()), msg);
    eprintln!("nameos: {msg}");

    let Some(path) = log_file() else { return };
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    // Roll rather than grow forever. Best effort; a failed roll just means the
    // file keeps growing, which is not worth failing a launch over.
    if std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0) > MAX_LOG {
        let old = path.with_extension("log.1");
        let _ = std::fs::remove_file(&old); // Windows rename won't clobber
        let _ = std::fs::rename(&path, &old);
    }
    use std::io::Write;
    if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&path) {
        // One `write_all` of one short line: two instances launching together
        // interleave lines, not halves of a line.
        let _ = f.write_all(line.as_bytes());
        let _ = f.flush();
    }
}

/// Forward the `log` crate's own records into `note()`, so anything tauri or
/// wry log internally lands in OUR log and stderr for the first time.
///
/// **THE GAP THIS CLOSES, FOUND BY READING THE VENDORED SOURCE, NOT
/// GUESSED.** `tauri-runtime-wry` handles a failed window/webview creation
/// with exactly one line — `Err(e) => log::error!("{e}")` — in its event
/// loop's `Message::CreateWindow` and `Message::CreateWebview` handlers
/// (`tauri-runtime-wry-2.11.4/src/lib.rs`). **That is the actual code path a
/// WebView2 data-directory failure goes through.** It is NOT `preflight()`
/// below — that only proves the runtime is *installed*, not that a window
/// can be created with it, and it runs and returns long before any window is
/// attempted. Confirmed against `wry-0.55.1/src/webview2/mod.rs`: the
/// `data_directory` handed to `CreateCoreWebView2EnvironmentWithOptions`
/// comes from the very same value this file logs in
/// `ensure_webview_data_dir_ready()` below, and a failure creating it
/// surfaces nowhere but that one `log::error!` line.
///
/// **Nothing in this crate had ever called `log::set_logger`** — checked by
/// grep across the whole `src/` tree before writing this, not assumed — so
/// every one of those lines has always gone to the `log` crate's default
/// no-op sink. A release build has no stderr for it either
/// (`windows_subsystem = "windows"`, this file's own header). So on the exact
/// failure this module exists to catch, the single most relevant internal
/// error tauri produces was being thrown away, silently, every time.
///
/// Warn and above only — tauri's own routine chatter at Info/Debug is not
/// what a support log needs, and a flooded log is one nobody reads.
struct ForwardToNote;

impl log::Log for ForwardToNote {
    fn enabled(&self, metadata: &log::Metadata) -> bool {
        metadata.level() <= log::Level::Warn
    }

    fn log(&self, record: &log::Record) {
        if self.enabled(record.metadata()) {
            note(&format!("[{}] {}: {}", record.level(), record.target(), record.args()));
        }
    }

    fn flush(&self) {}
}

/// Install the forwarder above as the process's global logger.
///
/// **Best-effort, like everything else in this file.** If something else has
/// already claimed the global logger, `set_boxed_logger` returns `Err` and
/// this is a silent no-op — a diagnostic must never be the reason the app
/// fails to start, and fighting over the global logger slot is not a hill
/// worth dying on.
pub fn install_log_forwarder() {
    if log::set_boxed_logger(Box::new(ForwardToNote)).is_ok() {
        log::set_max_level(log::LevelFilter::Warn);
    }
}

/// Where WebView2 (Windows) / WebKitGTK (Linux) is told to keep its profile.
///
/// **THIS HAS TO MATCH TAURI'S OWN RESOLUTION OR THE LOGGED PATH IS A LIE.**
/// Read off `tauri-2.11.5/src/manager/webview.rs`: it forces
/// `data_directory` to `path().resolve(&identifier, BaseDirectory::LocalData)`
/// — but only on `cfg(any(target_os = "linux", target_os = "windows"))`.
/// macOS is excluded there on purpose: WKWebView is not handed a directory
/// the same way and manages its own storage, which is why this returns
/// `None` on macOS rather than a guess.
///
/// On Windows, `BaseDirectory::LocalData` is `%LOCALAPPDATA%`; joined with
/// the identifier that is `%LOCALAPPDATA%\ai.nameos.desktop` — WebView2 then
/// creates its own `EBWebView` subfolder inside whatever we hand it, which is
/// the folder actually named in the error this module exists to defend
/// against (see this file's header and `the handover doc`'s installer notes: "39.8
/// MB sitting in LOCALAPPDATA\${IDENT}\EBWebView").
///
/// Deliberately reuses `log_dir()`'s exact env-var resolution — the same
/// `LOCALAPPDATA` / `XDG_DATA_HOME` reads — rather than a second
/// implementation of "where does local data live" that could drift from it.
fn webview_data_dir() -> Option<PathBuf> {
    #[cfg(target_os = "windows")]
    {
        let local = std::env::var_os("LOCALAPPDATA")?;
        Some(PathBuf::from(local).join(IDENTIFIER))
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let base = std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .filter(|p| p.is_absolute())
            .or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".local/share")))?;
        Some(base.join(IDENTIFIER))
    }
    #[cfg(target_os = "macos")]
    {
        None
    }
}

/// What happened when we made sure a directory is one we can actually write
/// into.
#[derive(Debug, PartialEq, Eq)]
enum DirReady {
    /// It was already there and a real write succeeded — the ordinary case.
    AlreadyWritable,
    /// It existed but a write into it failed, so it was renamed aside (never
    /// deleted — see the doc on `ensure_writable_with_recovery`) and a fresh
    /// directory was created in its place, and that one writes fine.
    RecoveredByMovingAside(PathBuf),
}

/// Create `dir` if it does not exist yet and remove a file after writing it,
/// proving the directory is genuinely writable rather than trusting the
/// permission bits.
///
/// **WHY A REAL WRITE, NOT A METADATA CHECK.** `Path::metadata()` reading as
/// writable and a write actually succeeding are different questions on
/// Windows — an ACL, an antivirus lock, or a second running instance holding
/// the folder open (a documented real-world cause of this exact WebView2
/// error) all show up as a failed write and none of them show up in the
/// permission bits. This performs the same kind of operation WebView2 itself
/// is about to attempt, so a failure here is the same failure it would hit.
///
/// The probe filename carries the pid so two instances launching at once —
/// which is itself one of the documented causes of this error — do not
/// collide with each other while proving the directory is clear.
fn probe_write(dir: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(dir)?;
    let probe = dir.join(format!(".nameos-write-probe-{}", std::process::id()));
    std::fs::write(&probe, b"ok")?;
    std::fs::remove_file(&probe)
}

/// Make sure `dir` is writable, with one bounded recovery attempt if it is
/// not.
///
/// **THE RECOVERY IS A RENAME, NEVER A DELETE.** If an existing directory
/// cannot be written to, it is moved aside with a timestamped suffix and a
/// clean directory is created at the original path. The old one is left on
/// disk, untouched. It may hold a genuinely corrupt WebView2 profile, or the
/// real fault may be a transient lock that had nothing to do with the
/// directory's contents at all — either way, deleting a person's data
/// because we could not fully explain a failure is the wrong trade, and the
/// moved-aside copy is exactly what a support reply would want to see next.
///
/// Returns `Err` only when even the fresh directory cannot be written to —
/// at that point there is no further local recovery to try, and the caller's
/// job is to say so plainly rather than attempt a third thing blind.
fn ensure_writable_with_recovery(dir: &Path) -> std::io::Result<DirReady> {
    match probe_write(dir) {
        Ok(()) => Ok(DirReady::AlreadyWritable),
        Err(_) if dir.exists() => {
            let moved = dir.with_file_name(format!(
                "{}.unwritable-{}",
                dir.file_name().and_then(|n| n.to_str()).unwrap_or(IDENTIFIER),
                now_secs(),
            ));
            std::fs::rename(dir, &moved)?;
            probe_write(dir)?;
            Ok(DirReady::RecoveredByMovingAside(moved))
        }
        Err(e) => Err(e),
    }
}

/// Log the resolved WebView2/WebKitGTK data directory and prove it is
/// writable before Tauri ever tries to use it.
///
/// **THIS IS THE DEFENSE FOR THE FAULT MARK REPORTED AND WE COULD NOT
/// REPRODUCE.** His install was verified using the correct per-user folder
/// (13 clean launches logged), so whatever produced that error on his
/// machine is not reproduced here and its cause stays unknown — see
/// `the handover doc`. What this adds is real regardless of that cause: proactive
/// proof the directory is writable, tried BEFORE Tauri's own silent internal
/// attempt (see `install_log_forwarder`'s doc for why that attempt was
/// invisible), so the common shape of this failure is caught here with a
/// named path and a next step, instead of a raw OS dialog or nothing at all.
///
/// Called from `main` right after `preflight()`, still before any window is
/// attempted.
pub fn ensure_webview_data_dir_ready() {
    let Some(dir) = webview_data_dir() else {
        note("webview data dir: not applicable on this platform (macOS manages its own)");
        return;
    };
    note(&format!("webview data dir resolved to {}", dir.display()));

    match ensure_writable_with_recovery(&dir) {
        Ok(DirReady::AlreadyWritable) => {}
        Ok(DirReady::RecoveredByMovingAside(moved)) => {
            note(&format!(
                "webview data dir at {} could not be written to -- moved it aside to {} \
                 and created a clean one; the old copy was kept, not deleted",
                dir.display(),
                moved.display()
            ));
        }
        Err(e) => {
            note(&format!("webview data dir UNWRITABLE even after recovery: {e}"));
            #[cfg(windows)]
            fatal(
                "helloim.ai can't start",
                &format!(
                    "helloim.ai can't start because Microsoft Edge WebView2 can't read and \
                     write to its data folder:\n\n{}\n\n\
                     Nothing you've saved is lost -- this is the folder WebView2 keeps its \
                     own browser profile in, separate from your conversations, which live \
                     elsewhere.\n\n\
                     This is usually one of: another copy of helloim.ai already running \
                     (check the taskbar and system tray), antivirus or endpoint-protection \
                     software blocking that folder, or Windows permissions on it being wrong \
                     for your account.\n\n\
                     To fix it: close any other helloim.ai window and try again. If that \
                     doesn't help, delete the folder above and start helloim.ai again -- it \
                     will be recreated automatically.\n\n\
                     Technical detail: {e}",
                    dir.display()
                ),
            );
            #[cfg(not(windows))]
            {
                // Best-effort here, on purpose. This machine is also the dev box
                // this module is written and tested on (see the header's "never
                // a new reason the app does not start" rule), and WebKitGTK's
                // failure mode for an unwritable data dir is not the documented
                // Windows-specific one this module targets. Tauri's own creation
                // attempt is the backstop -- silent before this patch, now
                // forwarded through `install_log_forwarder`.
            }
        }
    }
}

/// Log every panic, wherever it happens, before the process disappears.
///
/// **THIS IS THE ONE THAT CATCHES THE MEASURED FAILURE**, because the GTK case
/// is a panic inside `tao` and `run()` never returns to be matched on.
///
/// It CHAINS the previous hook rather than replacing it, so the ordinary
/// developer experience — a panic message and a backtrace on a terminal — is
/// unchanged on a debug build. And it only logs: it does not exit, and it does
/// not raise a dialog. A hook that put a message box on screen for every panic
/// anywhere in the app would fire for faults that are not fatal and not
/// actionable, and a dialog nobody can act on is how people learn to click
/// through dialogs. The two places we KNOW are fatal and actionable raise their
/// own, deliberately.
pub fn install_panic_hook() {
    let previous = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let where_ = info
            .location()
            .map(|l| format!("{}:{}", l.file(), l.line()))
            .unwrap_or_else(|| "unknown location".into());
        let what = info
            .payload()
            .downcast_ref::<&str>()
            .map(|s| (*s).to_string())
            .or_else(|| info.payload().downcast_ref::<String>().cloned())
            .unwrap_or_else(|| "panic with no message".into());
        note(&format!("PANIC at {where_}: {what}"));
        previous(info);
    }));
}

/// Ask, before building anything, whether there is a webview to build on.
///
/// `tauri::webview_version()` is a re-export of wry's platform call. **The two
/// platforms answer very different questions and conflating them would be the
/// mistake here:**
///
///   * **Windows** — it calls `GetAvailableCoreWebView2BrowserVersionString`,
///     Microsoft's own detection entry point, which fails when the runtime is
///     missing or unusable. That is a real preflight, and it is strictly better
///     than the registry probe the installer does, because it answers "can this
///     process load it" rather than "did something once write a version here".
///   * **Linux / macOS** — it returns the *compiled-in* WebKit version and
///     cannot fail. It says nothing about whether a window will appear, which
///     is precisely the case that started all this. So on those platforms this
///     is a breadcrumb in the log and nothing more, and it is written down that
///     way rather than left to look like a check that passed.
///
/// Returns only on success; on Windows a failure is terminal by design — a
/// process that cannot create a webview has no second thing to try, and
/// continuing would land back in the silent hang this module exists to kill.
pub fn preflight() {
    match tauri::webview_version() {
        Ok(v) => note(&format!("webview runtime {v}")),
        Err(e) => {
            note(&format!("webview runtime UNAVAILABLE: {e}"));
            #[cfg(windows)]
            fatal(
                "helloim.ai can't start",
                &format!(
                    "helloim.ai draws its window with the Microsoft Edge WebView2 Runtime, and \
                     this PC doesn't have a working copy of it.\n\n\
                     Nothing is broken in helloim.ai and nothing you've saved is lost — it just \
                     can't put a window on screen until WebView2 is back.\n\n\
                     To fix it: install the Evergreen WebView2 Runtime from\n\
                     https://developer.microsoft.com/microsoft-edge/webview2/\n\
                     and start helloim.ai again. Running the helloim.ai installer again does the \
                     same job if that's easier.\n\n\
                     Technical detail: {e}"
                ),
            );
        }
    }
}

/// Say the thing, then stop. Used only where continuing is known to be silence.
///
/// On Windows it puts a real dialog on screen, because there is no console, no
/// window and no other way to reach the person standing in front of the
/// machine. Everywhere else the log line plus stderr is the channel.
///
/// The dialog names the log path so the next question ("where do I look?") is
/// already answered — the standard this house holds for an error state: what
/// happened, what it did about it, and what happens next.
pub fn fatal(headline: &str, detail: &str) -> ! {
    note(&format!("FATAL {headline} — {detail}"));

    #[cfg(windows)]
    {
        use windows_sys::Win32::UI::WindowsAndMessaging::{
            MessageBoxW, MB_ICONERROR, MB_OK, MB_SETFOREGROUND, MB_TOPMOST,
        };
        let where_ = log_file().map(|p| p.display().to_string()).unwrap_or_default();
        let body = if where_.is_empty() {
            detail.to_string()
        } else {
            format!("{detail}\n\nA log of this is at:\n{where_}")
        };
        let wide = |s: &str| s.encode_utf16().chain(std::iter::once(0)).collect::<Vec<u16>>();
        let (text, caption) = (wide(&body), wide(headline));
        // SAFETY: both buffers are NUL-terminated UTF-16 and outlive the call,
        // and a null HWND is the documented way to raise an owner-less dialog.
        // MB_TOPMOST because there is no window of ours for this to sit over —
        // without it the one thing we have to say can open behind everything.
        unsafe {
            MessageBoxW(
                std::ptr::null_mut(),
                text.as_ptr(),
                caption.as_ptr(),
                MB_OK | MB_ICONERROR | MB_SETFOREGROUND | MB_TOPMOST,
            );
        }
    }

    std::process::exit(1);
}

/// Set by `on_page_load` — the first honest evidence that a webview exists and
/// ran something.
static PAGE_LOADED: AtomicBool = AtomicBool::new(false);

/// Called from the page-load hook. Cheap, idempotent, and the only writer.
pub fn page_loaded() {
    if !PAGE_LOADED.swap(true, Ordering::SeqCst) {
        note("window is up");
    }
}

/// How long to wait before deciding nothing is going to appear.
///
/// Long enough that a cold start on a slow disk, behind an antivirus scan of a
/// freshly-installed binary, does not get called a failure — that would be a
/// false alarm in a log, which teaches whoever reads it to discount the log.
const WATCHDOG_SECS: u64 = 20;

/// Notice that no page ever loaded, and write down enough to act on.
///
/// **BE HONEST ABOUT WHAT THIS CAN AND CANNOT SEE.** It proves one thing: no
/// page finished loading within the window. That covers a webview that never
/// started, which is the class of failure being fixed. It does **not** cover a
/// webview that loads and then fails to *composite* — the page would report
/// itself loaded while the screen stayed empty — and I could not reproduce a
/// broken-GPU machine to find out which of those the original sighting was. So
/// the line it writes describes the symptom it actually observed and does not
/// claim a cause.
///
/// It logs and never raises a dialog: by this point a window may well be on
/// screen, and a message box over a working app would be a worse bug than the
/// one being reported.
pub fn watch_for_a_window_that_never_appears<R: tauri::Runtime>(app: tauri::AppHandle<R>) {
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_secs(WATCHDOG_SECS));
        if PAGE_LOADED.load(Ordering::SeqCst) {
            return;
        }
        use tauri::Manager;
        // "Does a window object exist and think it is visible" separates
        // "nothing was created" from "something was created and you cannot see
        // it", which are different faults with different owners.
        let visible = match app.get_webview_window("main") {
            Some(w) => match w.is_visible() {
                Ok(v) => if v { "window says visible" } else { "window says hidden" },
                Err(_) => "window would not answer",
            },
            None => "no window object at all",
        };
        note(&format!(
            "NO PAGE LOADED after {WATCHDOG_SECS}s — {visible}. \
             If the screen is empty, the webview did not start. {}",
            environment_hint()
        ));
    });
}

/// The one sentence a support reply would otherwise have to type out.
///
/// Deliberately reports the environment we did NOT set: naming the workaround
/// is not the same as shipping it, and shipping it is what this module's header
/// refuses to do.
fn environment_hint() -> String {
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let set = |k: &str| if std::env::var_os(k).is_some() { "set" } else { "unset" };
        format!(
            "Session: WAYLAND_DISPLAY {}, DISPLAY {}. \
             Workaround to test with, NOT shipped because it costs speed on every \
             healthy machine: WEBKIT_DISABLE_COMPOSITING_MODE=1 \
             WEBKIT_DISABLE_DMABUF_RENDERER=1 LIBGL_ALWAYS_SOFTWARE=1 (currently {}, {}, {}).",
            set("WAYLAND_DISPLAY"),
            set("DISPLAY"),
            set("WEBKIT_DISABLE_COMPOSITING_MODE"),
            set("WEBKIT_DISABLE_DMABUF_RENDERER"),
            set("LIBGL_ALWAYS_SOFTWARE"),
        )
    }
    #[cfg(windows)]
    {
        "On Windows this is almost always the WebView2 Runtime: reinstall it from \
         https://developer.microsoft.com/microsoft-edge/webview2/ or run the helloim.ai \
         installer again."
            .to_string()
    }
    #[cfg(target_os = "macos")]
    {
        "On macOS the webview is part of the system; a failure here is usually a \
         damaged install — reinstall helloim.ai."
            .to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A fresh scratch directory under `temp_dir()`, per the house pattern
    /// already used across this crate (`profile.rs`, `facts.rs`, `mcp.rs`,
    /// …) — never the shared `temp_dir()` itself, and the pid keeps two test
    /// runs from colliding.
    fn scratch(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!("nameos-startup-{name}-{}", std::process::id()))
    }

    /// The ordinary case: a brand new directory writes fine on the first try.
    #[test]
    fn probe_write_succeeds_on_a_fresh_directory() {
        let dir = scratch("probe-fresh");
        let _ = std::fs::remove_dir_all(&dir);
        assert!(probe_write(&dir).is_ok());
        assert!(dir.is_dir());
        // The probe file must not be left behind -- it is a test of
        // writability, not a marker.
        assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 0);
        std::fs::remove_dir_all(&dir).unwrap();
    }

    /// `probe_write` must actually FAIL when the directory cannot be
    /// created, proving this is a real write attempt and not a check that
    /// only ever succeeds. A read-only parent means `create_dir_all` for the
    /// child cannot make anything under it.
    #[cfg(unix)]
    #[test]
    fn probe_write_fails_when_the_parent_is_unwritable() {
        use std::os::unix::fs::PermissionsExt;
        let parent = scratch("probe-readonly-parent");
        let _ = std::fs::remove_dir_all(&parent);
        std::fs::create_dir_all(&parent).unwrap();
        std::fs::set_permissions(&parent, std::fs::Permissions::from_mode(0o555)).unwrap();

        let child = parent.join("child");
        let result = probe_write(&child);

        // Permissions restored before cleanup, whatever the assertion below
        // does -- a failed assertion must not leave an unremovable directory
        // behind for the next run.
        std::fs::set_permissions(&parent, std::fs::Permissions::from_mode(0o755)).unwrap();
        std::fs::remove_dir_all(&parent).unwrap();

        assert!(result.is_err(), "a write under a read-only parent must fail, not silently pass");
    }

    /// `ensure_writable_with_recovery` on a normal writable directory: no
    /// recovery needed, and it must not report one that did not happen.
    #[test]
    fn recovery_reports_already_writable_when_nothing_was_wrong() {
        let dir = scratch("recovery-ok");
        let _ = std::fs::remove_dir_all(&dir);
        assert_eq!(ensure_writable_with_recovery(&dir).unwrap(), DirReady::AlreadyWritable);
        std::fs::remove_dir_all(&dir).unwrap();
    }

    /// THE RECOVERY PATH ITSELF, proven against a real unwritable directory
    /// rather than reasoned about: make the directory exist but refuse
    /// writes into it (mode 555 -- a directory needs write+execute to create
    /// files inside it, so removing write is enough while still allowing it
    /// to be renamed by its parent, which is what the recovery does).
    /// Confirms all three promises in `ensure_writable_with_recovery`'s doc:
    /// the fresh directory at the original path is genuinely writable, the
    /// old one is moved aside rather than deleted, and its contents survive.
    #[cfg(unix)]
    #[test]
    fn recovery_moves_an_unwritable_directory_aside_and_recreates_it() {
        use std::os::unix::fs::PermissionsExt;
        let dir = scratch("recovery-unwritable");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        // Leave evidence in the old directory so "moved, not deleted" is
        // actually checked, not just claimed.
        std::fs::write(dir.join("sentinel"), b"old profile data").unwrap();
        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o555)).unwrap();

        let outcome = ensure_writable_with_recovery(&dir);

        let moved = match outcome {
            Ok(DirReady::RecoveredByMovingAside(ref p)) => p.clone(),
            other => panic!("expected a recovery, got {other:?}"),
        };

        assert!(dir.is_dir(), "a fresh directory must exist at the original path");
        assert!(probe_write(&dir).is_ok(), "the recreated directory must genuinely be writable");
        assert!(moved.is_dir(), "the old directory must still exist, moved aside");
        assert!(
            moved.join("sentinel").exists(),
            "the old directory's contents must survive the move -- recovery is a rename, never a delete"
        );

        // `moved` still carries the 555 mode it was renamed with -- rename
        // does not touch permissions -- so it has to be restored before it
        // can be cleaned up, same as `parent` is in the sibling tests.
        std::fs::set_permissions(&moved, std::fs::Permissions::from_mode(0o755)).unwrap();
        std::fs::remove_dir_all(&dir).unwrap();
        std::fs::remove_dir_all(&moved).unwrap();
    }

    /// THE GENUINELY UNRECOVERABLE CASE: even the freshly-created directory
    /// cannot be written to, because the PARENT itself refuses writes. This
    /// is what must reach `ensure_webview_data_dir_ready`'s `fatal()` path --
    /// proving `Err` is actually reachable, not just declared in the type.
    #[cfg(unix)]
    #[test]
    fn recovery_fails_when_even_a_fresh_directory_cannot_be_made() {
        use std::os::unix::fs::PermissionsExt;
        let parent = scratch("recovery-hopeless-parent");
        let _ = std::fs::remove_dir_all(&parent);
        std::fs::create_dir_all(&parent).unwrap();
        let dir = parent.join("id");
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o555)).unwrap();
        // The parent, not just the child, is unwritable -- so renaming the
        // child aside and creating a new one at the same path both fail.
        std::fs::set_permissions(&parent, std::fs::Permissions::from_mode(0o555)).unwrap();

        let result = ensure_writable_with_recovery(&dir);

        std::fs::set_permissions(&parent, std::fs::Permissions::from_mode(0o755)).unwrap();
        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o755)).unwrap();
        std::fs::remove_dir_all(&parent).unwrap();

        assert!(result.is_err(), "with no writable parent, recovery must report failure, not silently claim success");
    }

    /// Matches what this platform actually resolves — an absolute path under
    /// the bundle identifier, and NOT the log path (which has this file's own
    /// separate `logs` suffix). Only meaningful where `webview_data_dir`
    /// resolves at all; macOS's `None` is asserted directly in
    /// `webview_data_dir_is_none_on_macos_by_design`.
    #[cfg(any(windows, all(unix, not(target_os = "macos"))))]
    #[test]
    fn webview_data_dir_resolves_under_the_identifier_and_not_into_logs() {
        let dir = webview_data_dir().expect("expected a resolvable path on this platform");
        assert!(dir.is_absolute(), "a relative webview data dir follows the working directory");
        assert!(dir.to_string_lossy().contains(IDENTIFIER));
        assert_ne!(
            dir.file_name().and_then(|n| n.to_str()),
            Some("logs"),
            "webview_data_dir must be the bare identifier dir, not log_dir()'s logs subfolder"
        );
    }

    /// Documents the deliberate platform gap: Tauri does not force a
    /// `data_directory` on macOS (`cfg(any(linux, windows))` in its own
    /// source), so there is nothing correct for this function to return
    /// there, and `None` must mean exactly that rather than "resolution
    /// failed".
    #[cfg(target_os = "macos")]
    #[test]
    fn webview_data_dir_is_none_on_macos_by_design() {
        assert_eq!(webview_data_dir(), None);
    }

    /// `ForwardToNote` must actually filter by level, checked against the
    /// real `enabled()` the global logger would consult -- not the global
    /// logger itself, which is process-wide, can only ever be installed
    /// once, and would make this test order-dependent on every other test in
    /// the binary. Testing the struct's own logic directly is what proves
    /// the level filter without touching that shared, one-shot state.
    #[test]
    fn forward_to_note_only_passes_warn_and_error() {
        use log::Log;
        let logger = ForwardToNote;
        assert!(logger.enabled(&log::Metadata::builder().level(log::Level::Error).build()));
        assert!(logger.enabled(&log::Metadata::builder().level(log::Level::Warn).build()));
        assert!(!logger.enabled(&log::Metadata::builder().level(log::Level::Info).build()));
        assert!(!logger.enabled(&log::Metadata::builder().level(log::Level::Debug).build()));
        assert!(!logger.enabled(&log::Metadata::builder().level(log::Level::Trace).build()));
    }

    /// The duplicated constant, held honest.
    ///
    /// It is duplicated for a reason the doc comment gives; this is what stops
    /// the reason turning into an excuse. If somebody renames the bundle, this
    /// fails here rather than by writing the log somewhere nobody looks.
    #[test]
    fn the_identifier_matches_the_config() {
        let conf = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/tauri.conf.json"))
            .expect("tauri.conf.json is not where this test expects it");
        let v: serde_json::Value = serde_json::from_str(&conf).unwrap();
        assert_eq!(
            v["identifier"].as_str(),
            Some(IDENTIFIER),
            "startup::IDENTIFIER has drifted from tauri.conf.json — the log would \
             be written to a folder the uninstaller does not remove"
        );
    }

    /// THE OTHER DUPLICATED CONSTANT, HELD JUST AS HONEST -- found 2026-08-29.
    /// W4 fixed `Cargo.toml`'s version drifting from `tauri.conf.json`'s by
    /// hand, once, and left the class open: nothing stopped the NEXT commit
    /// bumping one and not the other, which is the identical shape of the bug
    /// that made every NameOS build report 0.1.0 forever while a hand-built
    /// copy called itself 0.2.0-fix6. `Cargo.toml`'s own comment says the two
    /// "are free to drift apart tomorrow" -- a comment is not a lock. This is
    /// the lock, same pattern as `the_identifier_matches_the_config` above:
    /// `tauri.conf.json`'s "version" is what the updater and Add/Remove
    /// Programs read (via ship-windows.sh and Tauri's own PackageInfo);
    /// `CARGO_PKG_VERSION` is what `main.rs`'s startup-log line and `mcp.rs`'s
    /// serverInfo read. Two different numbers for the same build is exactly
    /// what this test exists to make impossible to ship, not just to notice.
    #[test]
    fn the_cargo_version_matches_the_config() {
        let conf = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/tauri.conf.json"))
            .expect("tauri.conf.json is not where this test expects it");
        let v: serde_json::Value = serde_json::from_str(&conf).unwrap();
        assert_eq!(
            v["version"].as_str(),
            Some(env!("CARGO_PKG_VERSION")),
            "Cargo.toml's version has drifted from tauri.conf.json's -- the \
             updater and Add/Remove Programs (tauri.conf.json) and startup.log \
             / mcp.rs's serverInfo (CARGO_PKG_VERSION) would report two \
             different numbers for the one build"
        );
    }

    /// **THE APP MUST NEVER FORCE SOFTWARE RENDERING ON ITSELF.**
    ///
    /// The three `WEBKIT_DISABLE_*` / `LIBGL_ALWAYS_SOFTWARE` variables made the
    /// window appear on the machine where this was found, and setting them in
    /// the shipped app would close the bug report while making every healthy
    /// machine slower — a silent failure traded for a universal slowdown. This
    /// module NAMES them, in the log, for a person to try; naming is not the
    /// same as shipping, and this is what keeps the two apart when somebody
    /// later reads the log line and thinks "why don't we just set it".
    ///
    /// It scans the whole crate rather than this file, because the tempting
    /// place to add it is `main`, and a rule that only guards the file that
    /// states it guards nothing.
    #[test]
    fn nothing_in_this_crate_forces_software_rendering() {
        let src_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("src");
        let mut checked = 0usize;
        let mut stack = vec![src_dir];
        while let Some(dir) = stack.pop() {
            for entry in std::fs::read_dir(&dir).expect("src is unreadable").flatten() {
                let p = entry.path();
                if p.is_dir() {
                    stack.push(p);
                    continue;
                }
                if p.extension().map(|e| e != "rs").unwrap_or(true) {
                    continue;
                }
                let text = std::fs::read_to_string(&p).unwrap_or_default();
                for (n, line) in text.lines().enumerate() {
                    let sets_env = line.contains("set_var(") || line.contains(".env(");
                    let names_it = line.contains("WEBKIT_DISABLE")
                        || line.contains("LIBGL_ALWAYS_SOFTWARE")
                        || line.contains("WEBKIT_FORCE");
                    assert!(
                        !(sets_env && names_it),
                        "{}:{} forces software rendering on every machine: {}",
                        p.display(),
                        n + 1,
                        line.trim()
                    );
                }
                checked += 1;
            }
        }
        // A scan that returned clean because it scanned nothing is the failure
        // this assertion exists to stop.
        assert!(checked > 10, "only scanned {checked} files — the walk is broken, not the code");
    }

    /// A timestamp that is quietly wrong is worse than a raw epoch count, so
    /// the conversion is checked against dates that can be looked up.
    #[test]
    fn the_clock_reads_correctly() {
        assert_eq!(utc_stamp(0), "1970-01-01 00:00:00Z");
        assert_eq!(utc_stamp(1), "1970-01-01 00:00:01Z");
        // A leap day, and the day after it.
        assert_eq!(utc_stamp(1_709_164_800), "2024-02-29 00:00:00Z");
        assert_eq!(utc_stamp(1_709_251_199), "2024-02-29 23:59:59Z");
        assert_eq!(utc_stamp(1_709_251_200), "2024-03-01 00:00:00Z");
        // A century that is not a leap year is the case the naive version gets
        // wrong, and 2100 is inside the lifetime of a written-down timestamp.
        assert_eq!(utc_stamp(4_107_542_400), "2100-03-01 00:00:00Z");
        // The day this was written. THE FIRST VALUE PUT HERE WAS A YEAR OUT,
        // and the test caught it rather than the converter — every constant in
        // this list came from `date -u -d '<date>' +%s` afterwards, not from
        // arithmetic in someone's head. That is the point of asserting against
        // dates a person can look up.
        assert_eq!(utc_stamp(1_787_875_200), "2026-08-28 00:00:00Z");
    }

    /// The log has to land where the uninstaller already looks, and it has to
    /// be somewhere at all — a diagnostic with no path is a diagnostic nobody
    /// ever reads.
    #[test]
    fn the_log_goes_under_the_bundle_identifier() {
        let p = log_file().expect("no log path on this platform");
        assert!(p.to_string_lossy().contains(IDENTIFIER), "log escaped the bundle dir: {p:?}");
        assert!(p.ends_with("startup.log"));
        assert!(p.is_absolute(), "a relative log path follows the working directory");
    }

    /// Writing must never be able to take the app down with it — that would
    /// make the diagnostic a new cause of the fault it diagnoses.
    #[test]
    fn logging_survives_having_nowhere_to_write() {
        // No HOME, no LOCALAPPDATA, no XDG_DATA_HOME: `log_file()` returns None
        // on every platform and `note` must still be a no-op rather than a
        // panic. Env changes are process-wide, so they are put back.
        let keys = ["HOME", "LOCALAPPDATA", "XDG_DATA_HOME"];
        let saved: Vec<_> = keys.iter().map(|k| (*k, std::env::var_os(k))).collect();
        for k in keys {
            std::env::remove_var(k);
        }
        assert!(log_file().is_none(), "expected no resolvable log path");
        note("this must not panic");
        for (k, v) in saved {
            match v {
                Some(v) => std::env::set_var(k, v),
                None => std::env::remove_var(k),
            }
        }
    }

    /// The Windows message has a job: tell somebody staring at an empty desktop
    /// what happened and what to do. Assert the substance so a later tidy-up
    /// cannot quietly reduce it to "an error occurred".
    #[test]
    fn the_windows_wording_is_actionable() {
        // The literal lives in `preflight`; this reads the source so the test
        // cannot pass against a copy of the text that is no longer shipped.
        let src = include_str!("startup.rs");
        assert!(src.contains("developer.microsoft.com/microsoft-edge/webview2/"));
        assert!(src.contains("nothing you've saved is lost"));
        assert!(src.contains("Running the helloim.ai installer again"));

        /* A "no secret words appear in this file" assertion was written here
           and DELETED, because it could only ever fail on itself: the test
           reads its own source, so the word it searched for was present in the
           search. It would have gone green the moment it was weakened and red
           for a reason that had nothing to do with the dialog.

           There is no honest automated version of "this message leaks nothing"
           — the message is a literal, and reading it is the check. Saying that
           plainly beats a green tick that means nothing, which is the same
           lesson `memory.rs` already carries about a bounds test that proved
           the wrong side. */
    }

    // -- The log boundary redacts, rather than trusting every call site. ----

    /// THE TEST THE HARDENING PASS ASKED FOR, LITERALLY: build the kind of
    /// line a real call site could produce — an error message that happens to
    /// quote the header it just sent, the exact shape `redact_and_truncate`'s
    /// own tests simulate for the same reason — and prove the key is gone
    /// from what `note()` would actually write, not just from a design intent
    /// in a comment.
    #[test]
    fn a_bearer_token_never_reaches_the_line_note_builds() {
        let key = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789";
        let msg = format!("provider test failed: sent Authorization: Bearer {key}, got 401");
        let logged = redact_and_cap(&msg);
        assert!(!logged.contains(key), "the real key survived redaction: {logged}");
        assert!(logged.contains("[redacted]"), "{logged}");
        // The surrounding sentence is still readable — this is redaction, not
        // a wipe. A line that redacts everything is as useless as one that
        // redacts nothing; nobody can debug a blank.
        assert!(logged.contains("provider test failed"));
        assert!(logged.contains("got 401"));
    }

    /// A bare key with no `Bearer` in front of it — the shape a misplaced
    /// `format!("using key {key}")` would actually produce — is caught by the
    /// prefix check on its own, independent of the `Bearer` word.
    #[test]
    fn a_bare_key_with_no_bearer_word_is_still_redacted() {
        let key = "sk-or-v1-0123456789abcdef0123456789abcdef0123456789abcdef";
        let logged = redact_and_cap(&format!("using key {key} for this session"));
        assert!(!logged.contains(key));
        assert!(logged.contains("[redacted]"));
    }

    /// The floor exists so an ordinary short word starting `sk-` — there
    /// isn't a common English one, but a model or file name plausibly could
    /// — is not mangled by a scan built to catch forty-character secrets.
    #[test]
    fn a_short_sk_prefixed_word_is_left_alone() {
        assert_eq!(redact_secret_shapes("the sk-8 variant shipped"), "the sk-8 variant shipped");
    }

    /// Ordinary text with no secret shape in it must come back byte-identical
    /// — a redaction pass that rewrites innocent lines is its own bug.
    #[test]
    fn an_ordinary_message_is_unchanged() {
        let msg = "starting helloim.ai 0.2.0";
        assert_eq!(redact_and_cap(msg), msg);
    }

    /// The cap is real, and it survives a multibyte character sitting right
    /// on the cut point — the exact panic `redact_and_truncate` was already
    /// hardened against in `providers.rs`; this proves the log boundary
    /// actually reuses that hardening rather than a fresh, untested cut.
    #[test]
    fn a_huge_message_is_capped_without_panicking() {
        let mut msg = "x".repeat(LOG_LINE_CAP - 1);
        msg.push('é');
        msg.push_str(" and then a great deal more text after the cut point");
        let logged = redact_and_cap(&msg);
        assert!(logged.len() <= LOG_LINE_CAP);
    }
}
