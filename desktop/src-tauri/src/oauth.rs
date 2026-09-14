//! Signing in to a hosted connector, the way an end user expects.
//!
//! Mark, 2026-08-26: *"we are setting this up for end users not us.. so we need
//! to think like that."* He said it after I proudly reported that his Gmail was
//! already connected — true, and true only because HE has connectors set up on
//! his own Claude account. A person who installs this tomorrow has none, and
//! telling them to go and configure things on a website is not a product.
//!
//! **WHAT AN END USER SHOULD GET**, and what he described watching a competitor
//! do: press Connect, the browser opens, they sign in to their own Notion or
//! Slack account, and it works. No API key to find in a settings page nobody
//! can navigate, no subscription to a middleman, no developer account.
//!
//! **WHY THAT IS POSSIBLE WITHOUT REGISTERING NAMEOS ANYWHERE.** These servers
//! publish `/.well-known/oauth-authorization-server` with a
//! `registration_endpoint` — dynamic client registration. The app registers
//! itself at the moment somebody presses Connect and gets a client id back.
//! Checked against Notion, Linear, Canva and Slack before this file existed;
//! all four advertise it.
//!
//! **THE PIECES, and each one is here because leaving it out breaks something
//! specific:**
//!
//! - **PKCE.** The redirect lands on a loopback port that any other program on
//!   the machine could also have been listening on. Without the code verifier,
//!   an authorization code seen by anything else is usable. With it, it is not.
//! - **`state`, checked on return.** A browser can be sent to our callback by
//!   any page on the internet. Without this we would happily exchange a code
//!   that somebody else's site handed us.
//! - **One-shot loopback listener on a port the OS picks.** A fixed port is one
//!   more thing that can already be in use, and a listener that outlives the
//!   flow is a hole left open for no reason.
//! - **A timeout.** Somebody closes the tab and walks away; a thread waiting
//!   forever on a socket is a leak that never announces itself.
//!
//! The token goes into the OS credential store through `connectors.rs`, which
//! already refuses to write a secret to disk. Nothing here changes that rule.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::time::Duration;

/// How long to wait for somebody to finish signing in before giving up. Long
/// enough to find a password, short enough that an abandoned attempt does not
/// hold a socket open for the rest of the session.
const WAIT: Duration = Duration::from_secs(300);
const NET: Duration = Duration::from_secs(20);

#[derive(Debug, Deserialize)]
struct Meta {
    authorization_endpoint: String,
    token_endpoint: String,
    #[serde(default)]
    registration_endpoint: String,
}

#[derive(Debug, Serialize)]
pub struct Signed {
    /// The bearer token to store. Never returned to the front end — see the
    /// caller in `connectors.rs`.
    pub access_token: String,
    pub refresh_token: String,
    /// WHO they signed in as, when the service says so. Mark, 2026-08-26: "if
    /// it is connected, it needs to show what username it is connected with".
    /// He is right that a green dot with no name is half an answer — on a
    /// machine with two Slack accounts it is no answer at all.
    /// Best effort by design: not every token response carries it, and an
    /// invented name would be worse than a blank. Empty means we do not know,
    /// and the window says nothing rather than guessing.
    pub account: String,
}

fn b64url(bytes: &[u8]) -> String {
    // base64url without padding, by hand. One small function against a
    // dependency whose only job here is thirty lines of table lookup.
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for chunk in bytes.chunks(3) {
        let b = [chunk[0], *chunk.get(1).unwrap_or(&0), *chunk.get(2).unwrap_or(&0)];
        let n = ((b[0] as u32) << 16) | ((b[1] as u32) << 8) | b[2] as u32;
        out.push(T[(n >> 18) as usize & 63] as char);
        out.push(T[(n >> 12) as usize & 63] as char);
        if chunk.len() > 1 { out.push(T[(n >> 6) as usize & 63] as char); }
        if chunk.len() > 2 { out.push(T[n as usize & 63] as char); }
    }
    out
}

/// Enough entropy for a verifier and a state value, without pulling in a
/// random-number crate: the OS gives us this directly.
fn nonce() -> String {
    let mut buf = [0u8; 32];
    getrandom(&mut buf);
    b64url(&buf)
}

#[cfg(unix)]
fn getrandom(buf: &mut [u8]) {
    use std::io::Read;
    // /dev/urandom is the OS's own generator; nothing here is rolling its own.
    let mut f = std::fs::File::open("/dev/urandom").expect("no /dev/urandom");
    f.read_exact(buf).expect("could not read random bytes");
}

#[cfg(windows)]
fn getrandom(buf: &mut [u8]) {
    #[link(name = "bcrypt")]
    extern "system" {
        fn BCryptGenRandom(h: *mut core::ffi::c_void, p: *mut u8, c: u32, f: u32) -> i32;
    }
    // BCRYPT_USE_SYSTEM_PREFERRED_RNG — the platform's own CSPRNG.
    let ok = unsafe { BCryptGenRandom(std::ptr::null_mut(), buf.as_mut_ptr(), buf.len() as u32, 2) };
    assert!(ok == 0, "BCryptGenRandom failed");
}

/// Every endpoint in the discovery document comes off the network, and the
/// document is served by whoever the user is trying to connect to.
///
/// **THE SCAR: `authorization_endpoint` WAS THE ONE VALUE IN THIS FILE THAT WAS
/// NEVER PASSED THROUGH `urlencode`.** Cassandra, 2026-08-28. It is pasted
/// straight into the URL built below and then handed to `open()`, which on
/// Windows went to `cmd.exe` — so a hosted connector could answer this request
/// with `"authorization_endpoint": "https://ok.example/a&<command>&"` and get
/// it run when the user pressed Sign in. `connectors.rs` no longer gives cmd a
/// command line to parse, and this is the other half: the string is checked at
/// the point it enters the program, so no future caller inherits a raw one.
///
/// **WHAT IS ENFORCED, AND WHERE IT COMES FROM.** RFC 6749 §3.1
/// (<https://www.rfc-editor.org/rfc/rfc6749#section-3.1>):
///
/// > "the authorization server MUST require the use of TLS"
/// > "The endpoint URI MAY include an 'application/x-www-form-urlencoded'
/// > formatted query component ... which MUST be retained when adding
/// > additional query parameters."
/// > "The endpoint URI MUST NOT include a fragment component."
///
/// So: https only, no fragment, an existing query is kept (see the join
/// below), and none of the characters that RFC 3986 does not permit unescaped
/// in a URI — which is the same set that makes a string dangerous to hand to
/// any shell, so one rule buys both.
fn checked_endpoint(raw: &str, what: &str) -> Result<String, String> {
    let url = raw.trim();
    // A URL long enough to be a problem is not a URL anybody meant to publish.
    if url.is_empty() || url.len() > 2048 {
        return Err(format!("Its sign-in description gave an unusable {what}."));
    }
    // RFC 6749 §3.1: TLS is required. This also refuses `file:`, `ms-settings:`
    // and anything else a scheme-blind check would have let through.
    if !url.starts_with("https://") {
        return Err(format!(
            "Its {what} is not an https address, so we stopped rather than sending \
             your sign-in over it."
        ));
    }
    // Something has to be there after the scheme.
    let rest = &url["https://".len()..];
    let host = rest.split(['/', '?', '#']).next().unwrap_or("");
    if host.is_empty() {
        return Err(format!("Its sign-in description gave an unusable {what}."));
    }
    // RFC 6749 §3.1: no fragment. Ours would be lost behind it anyway.
    if url.contains('#') {
        return Err(format!("Its {what} carries a fragment, which is not allowed here."));
    }
    /* Characters RFC 3986 does not allow unescaped in a URI. `&` is NOT in this
       list and must not be — it is legal in a query and every OAuth URL has
       one. The defence against `&` is that the URL never reaches a command-line
       parser (connectors.rs), not that we ban a legal character and break real
       services. */
    const FORBIDDEN: &[char] =
        &[' ', '"', '\'', '<', '>', '\\', '^', '`', '{', '}', '|', '\t', '\n', '\r'];
    if url.chars().any(|c| c.is_control() || FORBIDDEN.contains(&c)) {
        return Err(format!(
            "Its {what} contains characters that are not valid in a web address, so it \
             was refused."
        ));
    }
    Ok(url.to_string())
}

fn discover(url: &str) -> Result<Meta, String> {
    let base = {
        let u = url.trim_end_matches('/');
        let after = u.split("://").nth(1).unwrap_or(u);
        let host = after.split('/').next().unwrap_or(after);
        format!("https://{host}")
    };
    // The spec's own location, and the one all four probed servers answered on.
    let doc = ureq::get(&format!("{base}/.well-known/oauth-authorization-server"))
        .timeout(NET)
        .call()
        .map_err(|e| format!("This service does not offer a sign-in we can drive: {e}"))?
        .into_string()
        .map_err(|e| e.to_string())?;
    let mut meta: Meta = serde_json::from_str(&doc)
        .map_err(|e| format!("Its sign-in description could not be read: {e}"))?;

    /* CHECKED HERE, ONCE, RATHER THAN AT EACH USE. This is the only place a
       Meta is constructed, so a validated one is the only kind that exists and
       nothing downstream has to remember. `registration_endpoint` is optional —
       empty is a real answer meaning "set this up by hand" — but a non-empty
       one is held to the same rule. */
    meta.authorization_endpoint = checked_endpoint(&meta.authorization_endpoint, "sign-in address")?;
    meta.token_endpoint = checked_endpoint(&meta.token_endpoint, "token address")?;
    if !meta.registration_endpoint.trim().is_empty() {
        meta.registration_endpoint =
            checked_endpoint(&meta.registration_endpoint, "registration address")?;
    }
    Ok(meta)
}

/// Register this copy of the app and return a client id.
fn register(meta: &Meta, redirect: &str) -> Result<String, String> {
    if meta.registration_endpoint.trim().is_empty() {
        return Err("This service needs an account set up with them by hand.".into());
    }
    let body = serde_json::json!({
        "client_name": "helloim.ai",
        "redirect_uris": [redirect],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    });
    let res = ureq::post(&meta.registration_endpoint)
        .timeout(NET)
        .set("content-type", "application/json")
        .send_string(&body.to_string())
        .map_err(|e| format!("Could not register with the service: {e}"))?
        .into_string()
        .map_err(|e| e.to_string())?;
    serde_json::from_str::<serde_json::Value>(&res)
        .ok()
        .and_then(|v| v.get("client_id").and_then(|c| c.as_str()).map(str::to_string))
        .ok_or_else(|| "The service registered us but did not say who we are.".to_string())
}

/// Wait on the loopback redirect and return the `code`, having checked `state`.
fn await_code(listener: TcpListener, want_state: &str) -> Result<String, String> {
    listener
        .set_nonblocking(false)
        .map_err(|e| e.to_string())?;
    let deadline = std::time::Instant::now() + WAIT;

    for stream in listener.incoming() {
        if std::time::Instant::now() > deadline {
            return Err("Sign-in timed out.".into());
        }
        let Ok(mut stream) = stream else { continue };
        let mut line = String::new();
        if BufReader::new(&stream).read_line(&mut line).is_err() {
            continue;
        }
        // "GET /callback?code=…&state=… HTTP/1.1"
        let target = line.split_whitespace().nth(1).unwrap_or("");
        let query = target.split_once('?').map(|(_, q)| q).unwrap_or("");
        let mut code = String::new();
        let mut state = String::new();
        for pair in query.split('&') {
            let (k, v) = pair.split_once('=').unwrap_or((pair, ""));
            let v = percent_decode(v);
            match k {
                "code" => code = v,
                "state" => state = v,
                _ => {}
            }
        }

        let ok = !code.is_empty() && state == want_state;
        // THE PAGE THEY LAND ON. They are staring at a browser tab; leaving it
        // blank makes a completed sign-in look like a failure.
        let msg = if ok {
            "<h2>Connected.</h2><p>You can close this tab and go back to helloim.ai.</p>"
        } else {
            "<h2>That did not work.</h2><p>Go back to helloim.ai and try again.</p>"
        };
        let _ = write!(
            stream,
            "HTTP/1.1 200 OK\r\ncontent-type: text/html; charset=utf-8\r\n\
             content-length: {}\r\nconnection: close\r\n\r\n{}",
            msg.len(),
            msg
        );
        let _ = stream.flush();

        if !ok {
            // A mismatched state is the attack this check exists for; say so
            // plainly rather than retrying and hoping.
            return Err(if code.is_empty() {
                "The service did not send a sign-in code back.".into()
            } else {
                "The sign-in came back from somewhere unexpected and was refused.".to_string()
            });
        }
        return Ok(code);
    }
    Err("Sign-in was closed before it finished.".into())
}

fn percent_decode(s: &str) -> String {
    let b = s.replace('+', " ");
    let bytes = b.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() {
            if let Ok(v) = u8::from_str_radix(&b[i + 1..i + 3], 16) {
                out.push(v);
                i += 3;
                continue;
            }
        }
        out.push(bytes[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// The whole flow. Blocking, and called from an async command so the window
/// keeps painting while somebody is off in their browser.
pub fn sign_in(url: &str, open: impl Fn(&str)) -> Result<Signed, String> {
    let meta = discover(url)?;

    // Port 0: the OS picks a free one. A fixed port is one more thing that can
    // already be taken, on a machine we know nothing about.
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|e| e.to_string())?;
    let port = listener.local_addr().map_err(|e| e.to_string())?.port();
    let redirect = format!("http://127.0.0.1:{port}/callback");

    let client_id = register(&meta, &redirect)?;

    let verifier = nonce();
    let challenge = b64url(&Sha256::digest(verifier.as_bytes()));
    let state = nonce();

    /* `?` OR `&`, DECIDED BY WHAT THE ENDPOINT ALREADY HAS. RFC 6749 §3.1: the
       endpoint URI "MAY include an 'application/x-www-form-urlencoded'
       formatted query component ... which MUST be retained when adding
       additional query parameters." Hard-coding `?` produced a URL with two of
       them against any server that publishes one — malformed, and it would
       have failed with a message about neither end. Endpoints with a query are
       uncommon but legal, and this is a correctness fix as much as a tidy one. */
    let join = if meta.authorization_endpoint.contains('?') { '&' } else { '?' };
    let auth = format!(
        "{}{join}response_type=code&client_id={}&redirect_uri={}&state={}\
         &code_challenge={}&code_challenge_method=S256",
        meta.authorization_endpoint,
        urlencode(&client_id),
        urlencode(&redirect),
        urlencode(&state),
        urlencode(&challenge),
    );
    open(&auth);

    let code = await_code(listener, &state)?;

    let form = format!(
        "grant_type=authorization_code&code={}&redirect_uri={}&client_id={}&code_verifier={}",
        urlencode(&code),
        urlencode(&redirect),
        urlencode(&client_id),
        urlencode(&verifier),
    );
    let res = ureq::post(&meta.token_endpoint)
        .timeout(NET)
        .set("content-type", "application/x-www-form-urlencoded")
        .send_string(&form)
        .map_err(|e| format!("The service refused to finish the sign-in: {e}"))?
        .into_string()
        .map_err(|e| e.to_string())?;

    let v: serde_json::Value =
        serde_json::from_str(&res).map_err(|e| format!("Its answer could not be read: {e}"))?;
    let access = v
        .get("access_token")
        .and_then(|t| t.as_str())
        .ok_or_else(|| "The service did not return a token.".to_string())?;
    // Services put the identity in different places and most put it nowhere.
    // These are the ones seen in the wild; anything else leaves it blank.
    let account = ["account", "email", "user_email", "username", "user"]
        .iter()
        .find_map(|k| v.get(*k).and_then(|x| x.as_str()))
        .map(str::to_string)
        .or_else(|| {
            v.get("authed_user")
                .and_then(|u| u.get("id"))
                .and_then(|x| x.as_str())
                .map(str::to_string)
        })
        .or_else(|| {
            // Slack returns the workspace under `team`, which is the thing a
            // person recognises even though it is not their username.
            v.get("team")
                .and_then(|t| t.get("name"))
                .and_then(|x| x.as_str())
                .map(str::to_string)
        })
        .unwrap_or_default();

    Ok(Signed {
        access_token: access.to_string(),
        refresh_token: v
            .get("refresh_token")
            .and_then(|t| t.as_str())
            .unwrap_or_default()
            .to_string(),
        account,
    })
}

fn urlencode(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'.' | b'_' | b'~' => {
                out.push(b as char)
            }
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The challenge has to be the base64url of the SHA-256 of the verifier,
    /// unpadded. A padded or standard-alphabet value is rejected by the server
    /// with an error that says nothing about which of the two ends is wrong.
    #[test]
    fn pkce_challenge_matches_the_spec_example() {
        // RFC 7636 appendix B, the worked example every implementation is
        // checked against.
        let verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
        let challenge = b64url(&Sha256::digest(verifier.as_bytes()));
        assert_eq!(challenge, "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
    }

    #[test]
    fn b64url_has_no_padding_and_no_unsafe_characters() {
        for n in 1..40usize {
            let s = b64url(&vec![0xABu8; n]);
            assert!(!s.contains('='), "{n}: padded");
            assert!(!s.contains('+') && !s.contains('/'), "{n}: wrong alphabet");
        }
    }

    #[test]
    fn nonces_are_not_repeated() {
        let a = nonce();
        let b = nonce();
        assert_ne!(a, b);
        assert!(a.len() >= 43, "too short to be worth having");
    }

    /// The redirect carries values that arrive percent-encoded.
    #[test]
    fn it_decodes_what_a_browser_sends() {
        assert_eq!(percent_decode("a%2Fb%20c"), "a/b c");
        assert_eq!(percent_decode("plain"), "plain");
        assert_eq!(percent_decode("a+b"), "a b");
    }

    #[test]
    fn urlencode_escapes_everything_that_would_break_a_query() {
        assert_eq!(urlencode("a/b c&d=e"), "a%2Fb%20c%26d%3De");
        assert_eq!(urlencode("safe-._~"), "safe-._~");
    }

    /// The endpoint is the one value in this file that is NOT urlencoded — it
    /// cannot be, it is the address itself — so it is the one that has to be
    /// checked instead.
    #[test]
    fn a_hostile_authorization_endpoint_is_refused() {
        for bad in [
            // Characters RFC 3986 does not permit unescaped in a URI. They are
            // also every remaining shell metacharacter, which is the point.
            "https://ok.example/a|whoami",
            "https://ok.example/a^b",
            "https://ok.example/a b",
            "https://ok.example/a\"b",
            "https://ok.example/a`b`",
            "https://ok.example/a<b>",
            "https://ok.example/a\\b",
            "https://ok.example/a\nb",
            "https://ok.example/a\tb",
            "https://ok.example/a\0b",
            // RFC 6749 §3.1: no fragment.
            "https://ok.example/a#frag",
            // RFC 6749 §3.1: TLS is required. This is also what stops a
            // discovery document pointing us at a local handler instead of a
            // web address.
            "http://ok.example/a",
            "file:///etc/passwd",
            "ms-settings:privacy-microphone",
            "javascript:alert(1)",
            // Nothing to go to.
            "",
            "   ",
            "https://",
            "https:///path",
        ] {
            assert!(
                checked_endpoint(bad, "sign-in address").is_err(),
                "accepted a hostile endpoint: {bad:?}"
            );
        }
    }

    /// **`&` IS ACCEPTED HERE ON PURPOSE, AND THIS TEST EXISTS SO NOBODY
    /// "FIXES" THAT.** Cassandra's example payload was
    /// `https://ok.example/a&<command>&`, and it is a syntactically valid https
    /// URL: RFC 3986 lists `&` as a sub-delimiter, legal in a path and
    /// universal in a query — every OAuth URL we build contains four of them.
    ///
    /// So this validator cannot be what stops it, and pretending otherwise
    /// would put the defence in the wrong place while breaking real services.
    /// **What stops it is that the URL never reaches a command-line parser:**
    /// `connectors::open_in_browser` passes it to PowerShell in an environment
    /// variable, and its fallback is `explorer.exe`, which decodes arguments
    /// the standard way. The `cmd /C start` that made `&` dangerous is gone.
    ///
    /// If anyone ever puts a shell back in that path, this comment is the
    /// record that these strings were known to arrive here intact.
    #[test]
    fn ampersands_are_legal_and_are_defended_elsewhere() {
        for legal in [
            "https://ok.example/a?x=1&y=2",
            "https://ok.example/a&calc.exe&",
            "https://example.com/authorize?tenant=acme&mode=strict",
        ] {
            assert!(
                checked_endpoint(legal, "sign-in address").is_ok(),
                "refused a legal URL: {legal}"
            );
        }
    }

    /// Ordinary endpoints must pass untouched, whitespace-trimmed. A validator
    /// that rejects real services is one somebody deletes.
    #[test]
    fn real_endpoints_survive_validation() {
        for good in [
            "https://api.notion.com/v1/oauth/authorize",
            "https://linear.app/oauth/authorize",
            "https://slack.com/oauth/v2/authorize",
            "https://www.canva.com/api/oauth/authorize",
            "https://example.com/authorize?tenant=acme",
        ] {
            assert_eq!(
                checked_endpoint(good, "sign-in address").unwrap(),
                good,
                "rejected a real endpoint: {good}"
            );
        }
        assert_eq!(
            checked_endpoint("  https://ok.example/a  ", "x").unwrap(),
            "https://ok.example/a"
        );
    }

    /// RFC 6749 §3.1: an existing query "MUST be retained when adding
    /// additional query parameters". Hard-coding `?` produced two of them.
    #[test]
    fn a_query_already_on_the_endpoint_is_retained() {
        let with = "https://example.com/authorize?tenant=acme";
        let without = "https://example.com/authorize";
        let join = |e: &str| if e.contains('?') { '&' } else { '?' };
        assert_eq!(join(with), '&');
        assert_eq!(join(without), '?');
        assert_eq!(
            format!("{with}{}response_type=code", join(with)),
            "https://example.com/authorize?tenant=acme&response_type=code"
        );
        assert_eq!(
            format!("{without}{}response_type=code", join(without)),
            "https://example.com/authorize?response_type=code"
        );
    }
}
