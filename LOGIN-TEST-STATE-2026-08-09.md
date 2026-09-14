# Login page testing — full state, 2026-08-09

All three specialists finished. All three were killed by the same tool-host
outage (~09:40–13:17) before they could write anything to disk. Their findings
existed ONLY in the voice session's context — **this file is the salvage.** Do not
re-dispatch any of them to re-derive what is below.

Mark's standing approval, in his own words: *"you have approval for any changes
from this.."* — scoped to this work and whatever the same auth path turns up.
Irreversible actions still get a word first.

## Loose ends — RESOLVED, verified 13:17

The outage left a live board session cookie at `/tmp/beck-sess` (valid to
17:05:57) and two orphan test servers on `:18770` and `:8791`. **Checked at 13:17:
neither file exists and both ports are clear.** Nothing further to do; re-verify
rather than trusting this line if it matters.

## THE ONE THAT BITES MARK TODAY (~16:57:59)

His session was minted at 08:57:59 with an 8h TTL and **nothing re-mints on
activity**. When it expires **the board does not offer him a way back in.**

Beck traced it: the `/reconnect` bounce fires on two consecutive 401s from the
*say endpoint's* `/health` — the voice-line token, a different credential. Board
session expiry instead makes `/state` return **404 with a 9-byte non-JSON body**;
`r.json()` throws, the catch runs, the scene eases to idle. No status check, no
navigation. After 10s he gets a red **NOT CONNECTED** banner reading *"no answer
from the voice line"* — the wrong diagnosis, offering no sign-in route. Recovery
is a manual refresh he has no reason to know about.

Highest-value fix on the list. Due before ~17:00 today.

## Verdicts

- **Cassandra — the gate HOLDS against a stranger.** No credential, wrong
  credential, forged credential, forged origin, LAN-direct, replayed link: all
  refused. Her holes are in **evidence and revocation, not admission**.
- **Beck — GO on access, NOT SIGNED on durability.** Mark is in and can get back
  in from a genuine outside seat. She does not sign what she could not watch.
- **Tessa — design complete. APPROVED (below), not yet built.**

## Findings, worst first

1. **HIGH — no successful authentication is recorded on the board.**
   `_log_gate_refusal()` (server.py:901) is reached only from `_log_refused()`.
   `_handle_login_redeem()` (7879), `_redeem_ticket()` (5901), `_mint_session()`
   (5922) contain no logging call. `log_message` (8750) is suppressed unless
   `VISUALIZER_VERBOSE` is set; it is not set on the running board. **An
   unauthorised login would be invisible.** This is the approved build.
2. **MEDIUM — `/unlock` admits anyone who guesses one English word** inside a
   ten-minute window. Tessa insists it log as its own outcome (`ISSUED how=unlock`)
   rather than `how=cookie`, so the weakest route is not filed under the same label
   as the strongest. **Raised to Mark as a decision on its own merits, 2026-08-09.**
3. **MEDIUM — logout does not revoke a stolen cookie.** `_handle_logout` (7594)
   clears the browser's cookie and nothing else. `vlsession` is a bare HMAC with a
   self-contained expiry (`SESSION_TTL=28800`), no server-side store. A copied
   cookie works up to 8h after he logs out and, per finding 1, silently. Real
   revocation is only `server.py --revoke-logins`.
4. **MEDIUM — `_proxied()` is a three-name allow-list and the whole
   loopback-is-owner grant rests on it.** Proven: a loopback request carrying only
   `X-Real-IP: 203.0.113.9` got **200 on `/dashboard`** — `_proxied()` (7310) tests
   only `CF-Connecting-IP`, `X-Forwarded-For`, `Forwarded`. **Not exploitable
   today**; every real tunnel request carries `CF-Connecting-IP`. Any future proxy
   stamping only `X-Real-IP` turns every remote request into the owner.
5. **MEDIUM — the SMTP rewrite is not what is sending.** All 44 sends in
   `login.log` are `login link sent id=…`, the **legacy Gmail API path**. Zero
   `via smtp`, zero `smtp send failed` — `_smtp_secret()` returns None and falls
   through **silently**. Mail works; the stated primary transport is dead and the
   fallback is load-bearing. Ties to the open `00:50` request.
6. **LOW — `/build.txt` is documented as ungated and is gated** (server.py:8267).
   Safe direction, false comment; its stated purpose (a page checking its own
   freshness pre-session) does not work.
7. **LOW / unverified — `assets/sample.html` and `assets/samples.html`** (3,847 B
   each) are served to a stranger and documented nowhere. Content never inspected.

## The honesty finding — read before trusting any pass

**17 of Cassandra's 24 path tricks passed TRIVIALLY and she flagged it rather than
counting it.** Only 7 were real refusals (loopback 200 → stranger 404):
`/anything/dashboard.html`, `/a/b/c/d/dashboard`, `/ai/dashboard`, `//dashboard`,
`/trading`, `/working`, `/build`. The other 17 returned 404 from loopback too — no
such route. The backup-derivative rule that closed the 2026-08-05 hole is correct
**by reading** and **unproven live**: no backup derivative currently exists in
`assets/`.

## What genuinely held (verified live)

- Loopback vs proxied IS distinguished. Forged `CF-Connecting-IP` (127.0.0.1, ::1,
  duplicated), `X-Forwarded-For`, `Forwarded` — all refused at origin. Cloudflare
  also rejects client-supplied `CF-Connecting-IP` with 403 at the edge.
- LAN-direct to `10.0.0.227:8777` refused on all gated paths.
- `VOICE_LINE_TRUST_PROXIED` / `VOICE_LINE_OPEN_OWNER` **not set on the board**.
  The open-owner flag exists only on the client at :8898.
- 11 wrong-cookie variants → all 404, no 500. The `compare_digest`-on-str
  TypeError trap is closed.
- 14 magic-link abuse cases held on an isolated instance: junk, expired,
  one-char-swapped, replayed twice → 303→`/login?expired=1`, zero `Set-Cookie`.
  **8 concurrent redemptions of one ticket: exactly one winner.** The lock is real.
- Address field is not an oracle: 9 wrong-address variants → identical 303,
  byte-identical bodies (same md5), 2.4–3.0 ms, nothing written to the store.
- `/health` no longer leaks a passphrase; on :8777 it is not a route at all.
- **The private record holds harder than the board**: `/personal` is 404 even from
  loopback. `principal_for()` admits only a live owner or counsel session after an
  unconditional pinned-hostname check. Its own log holds 1,498 `refused` / 14
  `admit` **with** principal kind and identity tag — the private surface was never
  blind. Only the board is.

## Seat matrix (Beck, redirects suppressed)

| Seat | `/` | `/dashboard` | `/state` |
|---|---|---|---|
| loopback direct | 200 **no credential** | 200 | 200 |
| loopback + CF header | 303→/login | 404 | 404 |
| household LAN | 303→/login | 404 | 404 |
| public via Cloudflare | 303→/login | 404 | 404 |
| public + session cookie | 200 | 200 | 200 |

Loopback-direct is auto-admitted and **proves nothing** about the email flow.

## Live config

Board pid 291808 started 08:22:21; `server.py` mtime 08:18:41 — the live gate IS
current code. No env overrides. Link base `https://ai.markdalton.com`, ticket TTL
600s, session TTL 28800s.

**Mark's 08:57:59 redemption is nearly untraceable**: ticket issued 08:57:46,
`~/.voice-line-login.json` last written 08:57:59, now holds zero tickets. Only
`_redeem_ticket` removes without adding. That 13-second gap is the only trace on
the box **and the next link request overwrites it.**

## APPROVED DESIGN — gate success logging (Tessa)

Approved under Mark's standing grant. Build when picked up.

**Six ways in, not three.** Always log (credential *issuance*): magic-link
redemption; `?token=` link; **`/unlock`** (own outcome word — finding 2). Log
first-seen only (credential *presentation*): existing `vlsession`; existing
`vlboard`; loopback auto-admission. `accounts.py` runs before the gate with its own
sessions and log — out of scope, flagged so nobody reads a gap into it.

**Format** — outcome padded to 8 so existing `REFUSED` lines stay byte-compatible
and the refusal format does not move. `cookie=` dropped from success lines.

    2026-08-09 08:31:04  ADMIT    path=/          how=session   sid=9f3c1a20b4d7  peer=127.0.0.1  proxied=yes  cf_connecting_ip=…
    2026-08-09 09:14:55  ISSUED   path=/dashboard  how=unlock    sid=-  peer=127.0.0.1  proxied=yes  cf_connecting_ip=…
    2026-08-09 07:02:11  ADMIT    path=/state     how=loopback  sid=-  peer=127.0.0.1  proxied=no   cf_connecting_ip=-

Seat falls out of two fields: `proxied=no peer=127.0.0.1` on-box, `proxied=yes`
tunnel, `peer=10.0.0.x` LAN. Since `_from_loopback()` is false for LAN, an
`ADMIT how=loopback peer=10.0.0.x` line would itself be a finding.

**`sid = sha256(<full vlsession cookie value>)[:12]`** — NOT the cookie's own `sid`
component, which would be logging part of the credential. Same primitive as the
private gate's `_tag()`. **`sid=-` for `vlboard`**: one static shared value fixed at
process start, so its hash identifies nobody and would be a 48-bit commitment to a
live secret for zero audit value.

**Volume — the trap she caught.** `index.html:1190` sets `poll: 100` (10 Hz).
Natural experiment already in the log: 2026-08-08 18:36 has **944 `/state` lines in
one minute**; `/state` is **5,948 of 6,682 lines, 89%** of the file. Against
`logrotate.conf` (`size 1M, rotate 5`) at 134 B/line, naive success logging
**rotates every ~8 min and burns all five generations in ~42 min**, versus ~36h
retention today. Naive logging is a **net loss of the only security-relevant record
in the directory.**
**Suppression:** in-memory `identifier -> last_logged`, write on first-seen or after
`GATE_ADMIT_REPEAT = 3600`s, cap 512. Entries exist only for callers who passed, so
an attacker cannot grow it. In memory on purpose — a restart re-logs each live
session once, which is correct. Result: **~45 lines/day, +6 KB, ~0.7% of current
volume. No logrotate change needed.**

**Cause-number redaction is unconditional and lives in the LOG WRITER, not the call
sites** — bucket to first segment plus `*`. `board-gate.log` today contains zero
`legal` and no `/personal` path only because the private handler claims those paths
before `_is_gated` — **that is call order, not a guarantee**: if that module fails
its 0700/ownership checks the board treats it as absent and those paths fall
through to routing that logs `path` verbatim. A redaction at one call site is one
the next call site forgets, and this change adds four. Rejected a general path
allow-list: it would blind the refusal log to exactly the probing that caught a real
hole (`/dashboard.html.wren-backup-…`).

**Same file** — it is the *gate* log, not the refusal log; correlation ("six
refusals from this address, then an admit") is the real question and is one grep.
Rejected: a sibling (splits one record across two rotation clocks), JSON lines
(nothing parses this file), `login.log` (that is the mail-send log).

**Lockout defence is structural.** None of the seven gate predicates changes — **if
the diff touches one, send it back on sight.** `_log_admitted` returns `None` so it
cannot become load-bearing, is called after the decision and after the response is
sent, and reuses the existing `try/except Exception: pass` envelope so a full disk
is a silent no-op, never a 404. The single edit inside the gate is one assignment
(`self._admit_how = "cookie"`) before each existing `return True`. Deriving `how` by
re-calling `_cookie_ok()`/`_email_session_ok()` would evaluate credentials twice per
request and any divergence is a live lockout — that shape is to be refused.

**Before building:** read `server.py` ~8014–8098 in full (the `/dashboard` and
`/unlock` branches, one of four call sites). Tessa has it only from grep
(`8029 signed_in = …`, `8068 UNLOCK_WORD`, `8072 _set_cookie_and_redirect`); the
`/unlock` item is most likely to need adjusting. Also unverified: the 944/min figure
is measured on *refused* polls and assumes authenticated polls arrive at the same
rate (survives a 10× error). `accounts.py` (2,335 lines) not read — scoped out by
call order.

## Not completed — do not re-buy the rest

- Sustained 10 Hz poll — ran to completion, exit 0, output unread when host died.
- Session-cookie forgery battery — script built, never ran. Expiry and MAC
  verification established **by reading** `session_cookie.py:124-159`, not live.
- `SameSite=Strict` browser semantics — code only. **Worth chasing:** a Strict
  cookie is not sent on a cross-site-initiated navigation, so a link clicked *from
  an email* may land him on `/login` despite a live session.
- Rate-limit exhaustion — **deliberately skipped**; filling the 15/hr bucket would
  have locked Mark out for an hour. Correct call.
- Whether :8777 is reachable directly from the public internet (73.32.184.234).
- Content of `assets/sample.html` / `samples.html`.

## Next actions

1. Fix the expiry dead-end before ~17:00.
2. Build the approved logging design.
3. Then: logout revocation, `_proxied()` hardening, the SMTP silent fallback.
4. Close the ledger rows for all three — they completed, they did not stall.
