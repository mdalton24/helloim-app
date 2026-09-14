#!/usr/bin/env python3
"""drift-check.py — does this box still match what it says about itself?

Run it with no arguments. It prints NOTHING when everything agrees, so it is
cheap enough to run at the start of every session and at any point during one.

    python3 ~/Documents/JARVIS/drift-check.py        only what disagrees
    python3 ~/Documents/JARVIS/drift-check.py -v     also what was verified

    exit 0   everything checked, everything agreed
    exit 1   at least one thing disagrees
    exit 2   nothing disagreed, but at least one check could not run

WHY THIS EXISTS, in Mark's words on 2026-08-03: he asked, in earnest, whether
the problem was the hardware, the model or the team, because he kept having to
repeat himself and re-ask for things. Every failure that day was one shape:

  - a delegation rule written down twice and lapsed twice
  - CLAUDE.md saying "Seven specialists" with sixteen agent files on disk
  - ledger hooks matching a tool called `Task` when the dispatch tool here is
    `Agent` — they loaded, raised nothing, fired never, and the board showed an
    idle team all afternoon
  - a GREEN test suite through all of it, because it asserted the same wrong
    belief the code held
  - a roster showing four specialists working hours after they finished
  - four queue items rendered on the same screen as the decisions that killed
    them

Every one of those was a WRITTEN CLAIM THAT QUIETLY STOPPED MATCHING REALITY,
and in every case the only detector was Mark noticing. That made him the
monitoring system. This file exists so he is not.

THE THREE RULES IT OBEYS, and they matter more than any individual check:

  IT REPORTS. IT NEVER FIXES. A checker that repairs what it finds hides the
  RATE at which things break, and the rate is the diagnosis. Nothing in here
  writes a file, restarts a unit, or runs a command that changes anything.

  A CHECK THAT CANNOT RUN IS REPORTED AS A CHECK THAT COULD NOT RUN. Never as
  a pass. Silence from this program has to mean "verified", not "skipped",
  because the moment silence can also mean skipped the whole thing is worth
  nothing. Every check is wrapped so that an exception inside it becomes a
  visible "could not check" line naming the exception, and the exit code says
  so separately from drift.

  IT NEVER RAISES. A drift checker that crashes the session it is auditing is
  worse than no drift checker. The wrapper is the point, not laziness.

AND WHAT IT DELIBERATELY DOES NOT DO:

  No network, no root, no restarts, no writes. It reads files, asks systemd and
  the kernel what is running, and runs `git status`. That is the whole surface,
  and it is what makes it safe to run beside a live voice line mid-sentence.

  It does not fetch /status or any other endpoint, even on loopback. Adding an
  HTTP call would make this depend on a service being up and give it something
  that can hang; a checker you hesitate to run is a checker nobody runs.

  It does not try to check prose in general. See DOC_CLAIMS — that list is
  deliberately tiny and deliberately partial.

  IT NEVER NAMES THE THREE OMITTED SPECIALISTS. Three agent files are kept off
  the public roster because their titles alone disclose a private matter of
  Mark's, and they are gitignored for the same reason. A checker that helpfully
  reported "these three are on disk but not on the roster" would be the leak.
  Where a check needs that difference it uses the COUNT and never the names —
  see check_roster_omission_count, which is written that way on purpose and has
  a test asserting it.

Standard library only, system python3, no venv — same reasoning as the board's
server.py. A tool you have to activate an environment to run is a tool that
gets skipped when it matters.
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# --- Where things are ---------------------------------------------------------

HOME = Path.home()
JARVIS = Path(os.environ.get("JARVIS_DIR", HOME / "Documents" / "JARVIS"))
VAULT = Path(os.environ.get("JARVIS_VAULT", HOME / "Documents" / "ai-brain"))
VOICE_LINE = Path(os.environ.get("VOICE_LINE_ROOT", HOME / "voice-line"))
VISUALIZER = Path(os.environ.get("VOICE_VISUALIZER_ROOT", HOME / "voice-visualizer"))

AGENTS_DIR = JARVIS / ".claude" / "agents"
BOOT_CONFIG = JARVIS / "CLAUDE.md"
TEAM_NOTE = VAULT / "04 - Resources" / "The Team.md"
ONBOARDING = VAULT / "04 - Resources" / "Team Onboarding.md"

LOGS = VOICE_LINE / "logs"
ROSTER = LOGS / "team-status.json"
CLOUD_APPROVALS = LOGS / "cloud-approvals.json"

# ROSTER ROWS THAT ARE NOT PEOPLE AND MUST NEVER HAVE AN AGENT FILE.
#
# "sam" is the local GPU box, shown on the dashboard under its own name on
# Mark's instruction, 2026-08-11: "local GPU jobs should be referred to as Sam
# as the agent and listed as agent and shown as working on task like the other
# agents on the dashboard when working."
#
# THE ABSENCE OF `sam.md` IS THE POINT, NOT A FAULT. A session once read the
# hostname as a person, hired a specialist called Sam and began writing him into
# the vault; that file was deleted for exactly that reason. Creating it to
# silence this check would be the original mistake again, wearing a green tick
# as cover — see hooks/roster-truth.py, which carries the same warning beside
# the code that emits the row.
#
# THIS COST TWO CHECKS THEIR CREDIBILITY BEFORE IT WAS FIXED, 2026-08-12: the
# roster-names check named Sam as unreachable, and the omission count read 2
# instead of 3 because a row with no file skews the subtraction. Both were the
# CHECKER being wrong about a deliberate decision, which is the most expensive
# kind of false positive there is — a checker that cries wolf gets read as
# noise, and then the real drift underneath it is invisible.
NOT_PEOPLE = {"sam"}
LEDGER = LOGS / "team-tasks.jsonl"

BOARD_SOURCE = VISUALIZER / "server.py"
RUN_SERVERS = VOICE_LINE / "server" / "run-servers.sh"

# The public health probe and the tunnel that is supposed to answer it. See
# check_public_hostname for why these two files and why no DNS lookup.
VOICELINE_STATUS = VOICE_LINE / "systemd" / "voiceline-status"
CLOUDFLARED_CONFIGS = (
    Path("/etc/cloudflared/config.yml"),      # the live one the tunnel runs
    HOME / ".cloudflared" / "config.yml",     # the editable staging copy
)

# Every repo on this box. THERE IS NO REMOTE ON ANY OF THEM — checked, and the
# check below re-checks it rather than trusting this sentence — so uncommitted
# work is not "not pushed yet", it is one `rm -rf` or one dead session away from
# gone. Everything committed on 2026-08-03 was stranded at some point by a
# restart that killed the session holding it.
#
# markdalton-site ADDED 2026-08-04, and its absence was the exact failure this
# check exists to catch. It was watching four repos and this was not one of them,
# while it IS the repo holding the only two pages built for real people outside
# this house — Emma's salon draft and Bill Stradley's. Both were sitting fully
# UNTRACKED, along with assets/ and fonts/, so the checker reported a clean bill
# on the day the client work was the least protected thing on the box. A blind
# spot in a checker reads exactly like a pass, which is worse than no checker.
SITE = Path(os.environ.get("MARKDALTON_SITE_ROOT", HOME / "markdalton-site"))
REPOS = (VOICE_LINE, VISUALIZER, HOME / "local-llm", JARVIS, SITE)

# --- Thresholds ---------------------------------------------------------------

# How long a dispatch record stays believable. THIS MIRRORS THE BOARD'S
# TEAM_LEDGER_STALE_AFTER, and a mirrored constant is exactly the kind of claim
# this program exists to catch — so check_threshold_matches_board goes and reads
# the real one out of server.py rather than this file being trusted about it.
STALE_AFTER_S = 30 * 60

# How far the roster's hand-typed generated_at may lag the file's real mtime
# before it is worth saying out loud. An hour, because a stamp a few minutes
# behind the bytes is somebody finishing an edit, and six hours behind is a
# stamp describing a file that no longer exists in that form.
ROSTER_STAMP_LAG_S = 60 * 60

# A ledger with nothing recent in it is only interesting if something recent
# SHOULD have been recorded. See check_ledger_is_recording for why this is not
# a simple "the newest record is old" alarm.
LEDGER_QUIET_S = 6 * 60 * 60

# Findings are capped per check so one broken thing cannot produce a page of
# output nobody reads. The count is always reported in full; only the names are
# cut, and the line says so.
MAX_NAMES = 6

# Nothing here should take meaningful time. A command that hangs must cost one
# slow run, never a run that does not return.
CMD_TIMEOUT = 5.0


# --- Findings -----------------------------------------------------------------

DRIFT = "DRIFT"
UNCHECKED = "COULD NOT CHECK"


class Finding:
    """One disagreement, or one check that could not be made.

    `detail` lines are printed indented under the headline. They exist so a
    finding can name the actual files and timestamps rather than asserting
    something the reader has to go and confirm — the whole failure mode being
    fixed here is a confident sentence nobody checked.
    """

    __slots__ = ("kind", "check", "message", "detail")

    def __init__(self, kind: str, check: str, message: str,
                 detail: list[str] | None = None) -> None:
        self.kind = kind
        self.check = check
        self.message = message
        self.detail = detail or []


def drift(check: str, message: str, detail=None) -> Finding:
    return Finding(DRIFT, check, message, detail)


def unchecked(check: str, message: str, detail=None) -> Finding:
    return Finding(UNCHECKED, check, message, detail)


# --- Small shared helpers -----------------------------------------------------

def _run(args: list[str], cwd: Path | None = None) -> str | None:
    """stdout, or None if the command failed, timed out or is not installed.

    None is a "could not determine", and every caller has to turn it into an
    UNCHECKED finding rather than into a pass. That conversion is the single
    most important line in each check.
    """
    try:
        done = subprocess.run(args, capture_output=True, text=True,
                              timeout=CMD_TIMEOUT,
                              cwd=str(cwd) if cwd else None)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _ago(seconds: float) -> str:
    """A duration a person reads at a glance. Same shape as the board's _ago."""
    seconds = int(seconds)
    if seconds < 90:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 90:
        return f"{minutes} min"
    hours = minutes / 60
    if hours < 48:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} days"


def _clock(epoch: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(epoch))


def _names(items, limit: int = MAX_NAMES) -> str:
    items = list(items)
    shown = ", ".join(str(i) for i in items[:limit])
    if len(items) > limit:
        shown += f", and {len(items) - limit} more"
    return shown


NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    # PAST TWENTY, BECAUSE THE TEAM WALKED STRAIGHT OFF THE END OF THIS TABLE.
    # It stopped at "twenty" and the roster reached twenty-one on 2026-08-04, so
    # every headcount written out in words silently became unparseable and got
    # reported as "could not check" — which is not a pass. A bound that was fine
    # on the day it was written became a blind spot the moment the thing it
    # measures grew, and it did so quietly. Hyphen and space both, because both
    # get typed.
    "twenty-one": 21, "twenty one": 21, "twenty-two": 22, "twenty two": 22,
    "twenty-three": 23, "twenty three": 23, "twenty-four": 24, "twenty four": 24,
    "twenty-five": 25, "twenty five": 25, "twenty-six": 26, "twenty six": 26,
    "twenty-seven": 27, "twenty seven": 27, "twenty-eight": 28, "twenty eight": 28,
    "twenty-nine": 29, "twenty nine": 29, "thirty": 30, "thirty-one": 31,
    "thirty one": 31, "thirty-two": 32, "thirty two": 32, "thirty-three": 33,
    "thirty three": 33, "thirty-four": 34, "thirty four": 34, "thirty-five": 35,
    "thirty five": 35, "forty": 40, "fifty": 50,
}


def _as_number(word: str) -> int | None:
    """"sixteen" or "16" as an int, or None if it is neither.

    Written-out numbers because that is how these documents are written — "**
    Sixteen** specialists live in .claude/agents/" — and a checker that only
    understood digits would have missed the exact claim that went stale.
    """
    word = word.strip().strip("*_`").lower()
    if word.isdigit():
        try:
            return int(word)
        except ValueError:
            return None
    return NUMBER_WORDS.get(word)


# --- The process table, asked of systemd and then of the kernel ---------------

# The eight units, in the order the board lists them. This IS a declared list
# and there is no honest way around it — systemd cannot be asked "which units
# belong to the voice line". It is the one hardcoded table in this file, and
# check_unit_list_matches_board compares it against the board's own SERVICES
# tuple so that adding a ninth service in one place and not the other is itself
# reported as drift.
UNITS = (
    "voiceline-whisper.service",
    "voiceline-kokoro.service",
    "voiceline-voiceprint.service",
    "voiceline-client.service",
    "voiceline-board.service",
    "voiceline-brain.service",
    "voiceline-local-brain.service",
    "ollama.service",
)


def _unit_properties() -> dict[str, dict[str, str]] | None:
    """One systemctl call for all eight units. None if it could not be asked.

    Keyed off Id= rather than the order of the blocks, for the same reason the
    board does it: relying on output order matching argument order is an
    assumption nobody has written down anywhere.
    """
    out = _run(["systemctl", "--user", "show", *UNITS,
                "-p", "Id", "-p", "MainPID", "-p", "ActiveState",
                "-p", "ExecStart", "-p", "WorkingDirectory"])
    if out is None:
        return None
    states: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    for line in out.splitlines() + [""]:
        if not line.strip():
            if current.get("Id"):
                states[current["Id"]] = current
            current = {}
            continue
        key, _, value = line.partition("=")
        current[key] = value
    return states


_BTIME: float | None = None


def _boot_time() -> float | None:
    """Unix seconds at boot, from /proc/stat. Read once."""
    global _BTIME
    if _BTIME is not None:
        return _BTIME
    text = _read(Path("/proc/stat"))
    if text is None:
        return None
    for line in text.splitlines():
        if line.startswith("btime "):
            try:
                _BTIME = float(line.split()[1])
                return _BTIME
            except (ValueError, IndexError):
                return None
    return None


def _pid_start(pid: int) -> float | None:
    """When this pid actually started, in unix seconds, asked of the KERNEL.

    Not systemd's ExecMainStartTimestamp. systemd reports what it believes, and
    this house has twice put a green light over something whose MainPID no
    longer held its port — so the number that decides "is this process older
    than its source" comes from /proc, which cannot be wrong about it.

    Field 22 of /proc/<pid>/stat is start time in clock ticks since boot. It is
    parsed after the LAST ')' because field 2 is the executable name in
    parentheses and may itself contain spaces and parentheses; splitting the
    whole line on whitespace is the classic way this parse goes wrong.
    """
    text = _read(Path(f"/proc/{pid}/stat"))
    btime = _boot_time()
    if text is None or btime is None:
        return None
    try:
        after = text[text.rindex(")") + 1:].split()
        ticks = float(after[19])            # field 22, zero-based from field 3
    except (ValueError, IndexError):
        return None
    hz = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
    return btime + ticks / float(hz or 100)


_IMPORT = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)",
                     re.MULTILINE)


def _first_party_sources(entry: Path) -> set[Path]:
    """Every first-party .py file the entry script pulls in, transitively.

    Derived rather than declared, because a declared list of "the files this
    service runs" is one more claim that goes stale — which is the disease.

    HOW FAR IT REACHES, said plainly because the limit is the finding's
    accuracy: it follows top-level `import x` / `from x import` names, keeps
    only the ones that are a sibling .py file in the same directory, and
    repeats until nothing new turns up. So brain_server.py pulls in
    team_ledger.py, and local_brain_server.py pulls in brain_server.py and
    therefore team_ledger.py too — which is correct, and is exactly the link
    that mattered on 2026-08-03 when the hook fix sat committed and unloaded.

    WHAT IT DOES NOT REACH: site-packages, vendored trees, anything imported
    inside a function from a computed name, and any module in another
    directory. A static scan cannot see those without becoming an import
    machine, and importing a live server's source to find out what it imports
    is not a thing a read-only checker gets to do. The consequence is that this
    can UNDER-report — a stale dependency outside the entry's own folder will
    not be seen — and under-reporting is stated here rather than discovered.
    """
    folder = entry.parent
    siblings = {p.stem: p for p in folder.glob("*.py")}
    found = {entry}
    frontier = [entry]
    while frontier:
        current = frontier.pop()
        text = _read(current)
        if text is None:
            continue
        for name in _IMPORT.findall(text):
            sibling = siblings.get(name)
            if sibling is not None and sibling not in found:
                found.add(sibling)
                frontier.append(sibling)
    return found


def _exec_paths(exec_start: str) -> tuple[str | None, list[str]]:
    """(the binary systemd runs, its argv) out of an ExecStart property line.

    systemd renders it as `{ path=/x/y ; argv[]=/x/y a b ; ... }`, so both
    halves are pulled out by name rather than by position.
    """
    path = None
    argv: list[str] = []
    match = re.search(r"path=([^\s;]+)", exec_start)
    if match:
        path = match.group(1)
    match = re.search(r"argv\[\]=([^;]+)", exec_start)
    if match:
        argv = match.group(1).split()
    return path, argv


# --- CHECK 1: how many specialists does this system think it has? -------------

# The sentences that state a roster size, one anchored pattern per file.
#
# WHY THESE ARE PINNED TO A PHRASE INSTEAD OF SCANNING FOR "N specialists".
# The loose version was written first and it was WRONG IN THE WAY THAT MATTERS:
# it fired on CLAUDE.md's own account of the failure ("the board showing four
# specialists working hours after they finished... a boot file claiming seven
# specialists over sixteen") and on The Team's quotation of the stale line it
# was telling somebody to go and fix. Both of those are RECORDS OF DRIFT, not
# claims of fact, and a checker that cannot tell a description of a bug from
# the bug trains everyone to skip its output — which is the one failure this
# program cannot survive. So each pattern is anchored to the assertion it
# belongs to and matches nothing else.
#
# A FILE WHOSE PATTERN NO LONGER MATCHES IS REPORTED AS UNCHECKED, never as a
# pass. If somebody rewords the sentence, this check has lost its grip on that
# file and has to say so — the same discipline as the loopback claim below. A
# silently unanchored check is the disease, not the cure.
#
# THE LIST IS DELIBERATELY SHORT. Every note in the vault mentions the team;
# these three are the ones read at the start of a session and used to decide who
# to hand work to, which is what makes a wrong number in them cost something.
# Daily notes are deliberately absent and must stay absent — they are an
# append-only record of what was true on a day, so a daily note saying "seven"
# in a sixteen-person week is CORRECT.
ROSTER_CLAIMS = (
    (BOOT_CONFIG,
     re.compile(r"^\**([A-Za-z-]+|\d+)\**\s+specialists live in", re.MULTILINE),
     "the boot config's team section"),
    (TEAM_NOTE,
     re.compile(r"^\**([A-Za-z-]+|\d+)\**\s+specialists Jarvis delegates to",
                re.MULTILINE),
     "The Team's opening line"),
    (ONBOARDING,
     re.compile(r"written for all\s+([A-Za-z-]+|\d+)\s+of\s+\[\[The Team\]\]"),
     "the onboarding preamble"),
)

# The same shape again for the OTHER number that moves with the roster: how many
# specialists can reach the internet. The Team warns in its own words that
# retiring a web-enabled member "moves *both* numbers", which is a rule nobody
# is going to remember at the moment it applies. Counted from the frontmatter
# `tools:` line, which is what actually grants the tool.
WEB_CLAIMS = (
    (TEAM_NOTE,
     re.compile(r"\**([A-Za-z-]+|\d+)\**\s+of the\s+\**([A-Za-z-]+|\d+)\**\s+"
                r"can search and fetch"),
     "The Team's web-access line"),
    (ONBOARDING,
     re.compile(r"\**([A-Za-z-]+|\d+)\**\s+of the\s+\**([A-Za-z-]+|\d+)\**\s+"
                r"can search and fetch"),
     "the onboarding web-access line"),
)

_FRONTMATTER_TOOLS = re.compile(r"^tools:\s*(.+)$", re.MULTILINE)


def _agent_files() -> list[Path]:
    return sorted(AGENTS_DIR.glob("*.md"))


def check_cloud_approval_rows():
    """Does the cloud-approvals table still describe people who are here?

    THIS ONE HAS ALREADY FAILED, which is the only reason it exists. On
    2026-08-17 the table still carried a row for `rook`, retired the day before
    with the Training Dashboard. Nothing broke: the row simply gave a reason for
    sending work to the cloud on behalf of somebody who is not on the roster any
    more, and the dashboard rendered it as though it were current.

    THE COST IS TRUST, NOT FUNCTION, and that is the harder one to get back. A
    page that is right about nineteen rows and quietly wrong about the twentieth
    teaches the reader to check all twenty by hand, which is exactly the work
    this system exists to take off Mark.

    IT IS CHECKED IN ONE DIRECTION ONLY, deliberately. A row with no agent file
    is drift. An agent file with no row is NOT — `sable`, `holloway` and
    `redmond` are deliberately absent from published tables, and a checker that
    flagged their absence would be a checker that names them every time it runs.
    """
    if not AGENTS_DIR.is_dir():
        yield unchecked("cloud approval rows", "the agents directory is not readable")
        return
    blob = _read(CLOUD_APPROVALS)
    if blob is None:
        yield unchecked("cloud approval rows",
                        f"{CLOUD_APPROVALS.name} could not be read")
        return
    try:
        rows = json.loads(blob).get("rows") or []
        named = [str(r.get("agent", "")).strip().lower() for r in rows]
    except (ValueError, AttributeError, TypeError):
        yield unchecked("cloud approval rows",
                        f"{CLOUD_APPROVALS.name} is not the expected shape")
        return
    on_disk = {f.stem.lower() for f in _agent_files()}
    ghosts = sorted({n for n in named if n and n not in on_disk})
    if ghosts:
        yield drift("cloud approval rows",
                    f"{len(ghosts)} row(s) describe a specialist with no agent file",
                    _names(ghosts))


def check_agent_count():
    """Does anything that states a roster size still state the right one?

    THIS ONE HAS ALREADY FAILED. On 2026-08-03 CLAUDE.md said "Seven
    specialists live in .claude/agents/" with sixteen files sitting in that
    directory, and it had said so through a session that briefed people from
    it. The file now carries its own warning to count the directory; this is
    that warning made mechanical.
    """
    if not AGENTS_DIR.is_dir():
        yield unchecked("agent count",
                        f"{AGENTS_DIR} is not a directory, so nothing could be "
                        f"counted")
        return
    actual = len(_agent_files())
    if actual == 0:
        yield unchecked("agent count",
                        f"no agent files found in {AGENTS_DIR}; refusing to "
                        f"compare a count of zero against anything")
        return

    for path, pattern, description in ROSTER_CLAIMS:
        text = _read(path)
        if text is None:
            yield unchecked("agent count",
                            f"{path.name} could not be read, so its roster "
                            f"claim was not checked")
            continue
        matches = pattern.findall(text)
        if not matches:
            yield unchecked("agent count",
                            f"{path.name}: {description} no longer matches the "
                            f"sentence this check was written against, so its "
                            f"headcount was NOT verified — repoint the pattern")
            continue
        for raw in matches:
            stated = _as_number(raw)
            if stated is None:
                yield unchecked("agent count",
                                f"{path.name}: {description} says {raw!r}, "
                                f"which is not a number this check can read")
            elif stated != actual:
                yield drift("agent count",
                            f"{path.name} says {stated} specialists; "
                            f"{actual} agent files are on disk",
                            [f"in {description}"])


def check_web_access_count():
    """"Fourteen of the sixteen can search and fetch" — still both true?

    TWO NUMBERS IN ONE SENTENCE, which is why it is worth its own check: hiring
    or retiring anybody moves the second, and doing it to a web-enabled member
    moves both. The Team says so in its own prose, one paragraph away from the
    sentence, and a rule that lives only in prose is the thing that lapses.

    Counted from each agent file's frontmatter `tools:` line, because that is
    what actually grants the tool — not from any list of who was authorised.
    """
    if not AGENTS_DIR.is_dir():
        yield unchecked("web access count", "the agents directory is not readable")
        return
    files = _agent_files()
    if not files:
        yield unchecked("web access count", "no agent files to count")
        return
    total = len(files)
    web = 0
    unreadable = []
    for path in files:
        text = _read(path)
        if text is None:
            unreadable.append(path.name)
            continue
        match = _FRONTMATTER_TOOLS.search(text)
        if match and re.search(r"websearch|webfetch", match.group(1), re.I):
            web += 1
    if unreadable:
        yield unchecked("web access count",
                        f"{len(unreadable)} agent file(s) could not be read, so "
                        f"the web-enabled count is incomplete",
                        [_names(unreadable)])
        return

    for path, pattern, description in WEB_CLAIMS:
        text = _read(path)
        if text is None:
            yield unchecked("web access count",
                            f"{path.name} could not be read")
            continue
        matches = pattern.findall(text)
        if not matches:
            yield unchecked("web access count",
                            f"{path.name}: {description} no longer matches the "
                            f"sentence this check was written against, so it "
                            f"was NOT verified — repoint the pattern")
            continue
        for raw_web, raw_total in matches:
            said_web, said_total = _as_number(raw_web), _as_number(raw_total)
            if said_web is None or said_total is None:
                yield unchecked("web access count",
                                f"{path.name}: {description} carries numbers "
                                f"this check cannot read ({raw_web!r}, "
                                f"{raw_total!r})")
            elif (said_web, said_total) != (web, total):
                yield drift("web access count",
                            f"{path.name} says {said_web} of {said_total} can "
                            f"search and fetch; the frontmatter says {web} of "
                            f"{total}",
                            [f"in {description}"])


def check_roster_omission_count():
    """Does the roster's own "three are missing" line still say the right number?

    The board publishes the FACT and the COUNT of the specialists left off it,
    and never their names or roles, because that page may become publicly
    reachable and their titles alone would disclose a private matter. That
    sentence is hand-typed. Hire a seventeenth specialist and leave them off the
    roster and the sentence silently becomes wrong in the direction that
    under-reports — the same shape as a health check answering 200 over a
    service it never looked at.

    THIS CHECK IS WRITTEN TO BE INCAPABLE OF LEAKING WHAT IT IS ABOUT. It knows
    two integers, the number of agent files and the number of roster rows, and
    it never reads a name from either side. There is a test asserting that no
    output of this function can contain one.
    """
    if not AGENTS_DIR.is_dir():
        yield unchecked("omission count", "the agents directory is not readable")
        return
    on_disk = len(_agent_files())
    blob = _read(ROSTER)
    if blob is None:
        yield unchecked("omission count",
                        f"{ROSTER.name} could not be read")
        return
    try:
        data = json.loads(blob)
        rows = len(data.get("team") or [])
        sentence = data.get("omitted")
    except (ValueError, AttributeError, TypeError):
        yield unchecked("omission count",
                        f"{ROSTER.name} did not parse as the expected JSON")
        return

    # ROWS THAT ARE NOT PEOPLE DO NOT COUNT AGAINST THE FILES ON DISK. See
    # NOT_PEOPLE for why one of them exists. Without this the arithmetic is off
    # by exactly the number of machines on the roster, and it reports as though
    # a specialist had gone missing.
    try:
        rows = len([r for r in (data.get("team") or [])
                    if str(r.get("name", "")).strip().lower() not in NOT_PEOPLE])
    except (AttributeError, TypeError):
        pass

    missing = on_disk - rows
    if not isinstance(sentence, str) or not sentence.strip():
        if missing:
            yield drift("omission count",
                        f"{missing} specialist(s) are on disk but not on the "
                        f"roster, and the roster says nothing about it")
        return

    stated = None
    for raw in re.findall(r"\b([A-Za-z-]+|\d+)\b", sentence):
        value = _as_number(raw)
        if value is not None:
            stated = value
            break
    if stated is None:
        yield unchecked("omission count",
                        "the roster's omission sentence carries no number, so "
                        "it could not be compared against the count on disk")
        return
    if stated != missing:
        yield drift("omission count",
                    f"the roster says {stated} specialist(s) are deliberately "
                    f"left off it, but {on_disk} agent files minus "
                    f"{rows} roster rows is {missing}")


def check_roster_names_have_agents():
    """Every specialist on the roster still has an agent file to dispatch.

    ONE DIRECTION ONLY, and the asymmetry is deliberate. A roster name with no
    agent file is a row that puts a role and a title on somebody Jarvis cannot
    actually reach, so it is named. The other direction — an agent file that is
    not on the roster — is REPORTED ONLY AS A COUNT by check_roster_omission_count,
    because naming it is precisely the disclosure the roster is built to avoid.
    """
    blob = _read(ROSTER)
    if blob is None:
        yield unchecked("roster names", f"{ROSTER.name} could not be read")
        return
    if not AGENTS_DIR.is_dir():
        yield unchecked("roster names", "the agents directory is not readable")
        return
    try:
        rows = json.loads(blob).get("team") or []
        names = [str(r.get("name", "")).strip() for r in rows if isinstance(r, dict)]
    except (ValueError, AttributeError, TypeError):
        yield unchecked("roster names", f"{ROSTER.name} did not parse")
        return

    have = {p.stem.lower() for p in _agent_files()}
    orphans = [n for n in names
               if n and n.lower() not in have and n.lower() not in NOT_PEOPLE]
    if orphans:
        yield drift("roster names",
                    f"{len(orphans)} roster row(s) name somebody with no agent "
                    f"file: {_names(orphans)}",
                    ["the board shows them a title and a role; nothing can "
                     "actually be handed to them"])


# --- CHECK 2: is the ledger actually recording? -------------------------------

def check_ledger_is_recording():
    """Not "does the file exist" — is the HOOK ALIVE and writing.

    THE FAILURE THIS IS SHAPED BY. team_ledger.py registered its hooks against
    a tool named `Task`. The dispatch tool in this harness is `Agent`. Nothing
    raised, nothing logged, the hooks loaded cleanly and never fired once — so
    the board showed an idle team through an afternoon in which five
    specialists ran. A file that exists, parses and is stale looks identical to
    a file that is being kept up to date, from the outside.

    So this asks the question from the side that cannot be faked: EVERY RECORD
    WRITTEN BY THE HOOK CARRIES `"by": "hook"`, because team_ledger.append puts
    it there and nothing else does. Hand-written and backfilled records carry
    something else, and say so. If the recent history of the ledger contains no
    hook-written record at all, the hook is not recording, whatever the file
    looks like.

    That is a stronger test than "is the newest record old", which cannot tell
    a working hook on a quiet afternoon from a dead one on a busy morning.
    """
    if not LEDGER.exists():
        yield drift("ledger recording",
                    f"{LEDGER.name} does not exist, so no dispatch has ever "
                    f"been recorded")
        return
    text = _read(LEDGER)
    if text is None:
        yield unchecked("ledger recording", f"{LEDGER.name} could not be read")
        return

    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue                       # a torn last line is its normal state
        if isinstance(row, dict) and isinstance(row.get("ts"), (int, float)):
            rows.append(row)
    if not rows:
        yield drift("ledger recording",
                    f"{LEDGER.name} holds no usable records at all")
        return

    now = time.time()
    newest = max(r["ts"] for r in rows)
    by_hook = [r for r in rows if r.get("by") == "hook"]

    if not by_hook:
        yield drift("ledger recording",
                    f"not one of the {len(rows)} ledger records was written by "
                    f"the hook — every one is a hand-append or a backfill",
                    [f"newest record {_ago(now - newest)} old, at "
                     f"{_clock(newest)}",
                     "this is the 2026-08-03 shape exactly: the hooks load, "
                     "raise nothing, and never fire. Check that the brain has "
                     "restarted since team_ledger.py last changed, and that "
                     "its matcher names the dispatch tool this harness "
                     "actually uses."])
    elif now - max(r["ts"] for r in by_hook) > LEDGER_QUIET_S:
        # The hook has worked at some point, so this is softer: it may simply
        # be a quiet stretch. Said as an observation with its age attached
        # rather than as an accusation.
        quiet = now - max(r["ts"] for r in by_hook)
        yield drift("ledger recording",
                    f"the last hook-written ledger record is {_ago(quiet)} old, "
                    f"though {len(rows) - len(by_hook)} record(s) have been "
                    f"added by hand since")


def check_brain_has_the_ledger_code():
    """Is the running brain executing the team_ledger.py that is on disk?

    Called out separately from the whole-stack check below because this is the
    specific pairing that has already cost an afternoon: the hook fix was
    committed at lunchtime and the process kept running the version without it,
    so the code was right, the test was green, the file was correct, and the
    board still lied.
    """
    ledger_src = VOICE_LINE / "server" / "team_ledger.py"
    if not ledger_src.is_file():
        yield unchecked("brain ledger code",
                        f"{ledger_src} does not exist")
        return
    props = _unit_properties()
    if props is None:
        yield unchecked("brain ledger code",
                        "systemctl did not answer, so nothing about the "
                        "running brain is known")
        return
    info = props.get("voiceline-brain.service")
    if not info:
        yield unchecked("brain ledger code",
                        "systemd did not report voiceline-brain.service")
        return
    try:
        pid = int(info.get("MainPID", "0"))
    except ValueError:
        pid = 0
    if pid <= 0:
        yield unchecked("brain ledger code",
                        "voiceline-brain.service reports no MainPID, so the "
                        "running code could not be identified")
        return
    started = _pid_start(pid)
    if started is None:
        yield unchecked("brain ledger code",
                        f"the start time of pid {pid} could not be read from "
                        f"/proc, so nothing was compared")
        return
    changed = ledger_src.stat().st_mtime
    if changed > started:
        yield drift("brain ledger code",
                    f"the brain (pid {pid}) started at {_clock(started)} but "
                    f"team_ledger.py changed at {_clock(changed)} — it is "
                    f"running the older hooks",
                    ["dispatches are not being recorded by the version on "
                     "disk; the board's team panel will be wrong until the "
                     "brain restarts"])


# --- CHECK 3: stale specialist state -----------------------------------------

def check_open_dispatches():
    """A dispatch nobody closed, past the point where it still means "working".

    An open record is not evidence that somebody is working. It is evidence
    that somebody was dispatched and nothing closed it, and past the threshold
    those two readings diverge sharply — a session dying mid-task has happened
    here more than once. The board already ages these at read time; this says
    the same thing where a person will see it without opening the board.

    THE JOIN IS ON `tool_use_id`, AND THIS USED TO REDUCE BY MEMBER WITH
    NEWEST-ROW-WINS. That was wrong twice in twelve hours on 2026-08-05, in
    opposite directions, and both were the same mistake: a member is not a job.
    The overnight session died holding eleven dispatches; all eleven were
    re-dispatched at 06:52–06:54, and the closing rows for the dead ones were
    written at 06:54:50 — correct ids, but stamped with the CLEANUP time, which
    sorts after the replacement. Under the old rule every one of those members'
    newest row was a `failed` belonging to a job that had already been replaced,
    so eight live specialists read as finished and this check said nothing about
    any of them. Turn it round — a closing row stamped EARLIER than a dispatch it
    does not belong to — and the same rule reports a job somebody closed an hour
    ago.

    A specialist holding a dead dispatch and a live one at the same instant is
    not an edge case. It is what a re-dispatch IS, and it happens every time a
    session dies. So each JOB is tracked on its own id and the timestamps decide
    nothing except age.

    (hooks/jobs.py holds the same rule, and this deliberately does not import it.
    That file's docstring says two copies of a rule drift, and it is right — but
    this program's own docstring says standard library only, no first-party
    imports, so that a syntax error somewhere else in the repo cannot take out
    the checker that would tell you about it. The duplication is the price of
    that, and it is why both copies carry the same story.)
    """
    text = _read(LEDGER)
    if text is None:
        yield unchecked("open dispatches", f"{LEDGER.name} could not be read")
        return

    # `closed`, `stopped` and `cancelled` are what a hand-swept dispatch gets
    # when a later session writes the row a dead one could not write for itself.
    # They were absent from this list until 2026-08-05, so every job anybody had
    # tidied up by hand went on being reported as open.
    #
    # `died` joined them 2026-08-07, and it had already been WRITTEN to the
    # ledger before it was ever READ here — one row, months old, describing a
    # dispatch whose host was gone. A closing word this checker does not
    # recognise is worse than no closing word at all: the sweeper believes the
    # job is shut, the checker goes on reporting it open forever, and the two
    # disagree with nobody looking. If a future session invents another verb for
    # this, it belongs in this tuple in the same commit.
    terminal = ("completed", "failed", "closed", "stopped", "cancelled", "died")
    live: dict[str, dict] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        member = str(row.get("member", "")).strip().lower()
        event = row.get("event")
        ts = row.get("ts")
        if not member or event not in ("dispatched",) + terminal:
            continue
        if isinstance(ts, bool) or not isinstance(ts, (int, float)):
            continue
        # The same key hooks/jobs.py uses, fallback included: the oldest rows in
        # this ledger were hand-backfilled before the dispatch hook carried an
        # id, and member+task is what closes those.
        key = str(row.get("tool_use_id") or f"{member}:{row.get('task')}")
        if event == "dispatched":
            live[key] = {"ts": ts, "member": member, "task": row.get("task") or ""}
        else:
            live.pop(key, None)

    now = time.time()
    stale = [r for r in live.values() if now - r["ts"] > STALE_AFTER_S]
    for record in sorted(stale, key=lambda r: r["ts"])[:MAX_NAMES]:
        yield drift("open dispatches",
                    f"{record['member']} was dispatched "
                    f"{_ago(now - record['ts'])} ago and nothing closed it",
                    [str(record["task"])[:140] or "task not named in the record",
                     "either the work is still running, or the session holding "
                     "it died — the record cannot tell you which, which is why "
                     "it stops claiming 'working'"])


def check_roster_stamp():
    """Has the roster been edited without its own stamp moving?

    generated_at is HAND-TYPED, so it is a claim about the file rather than a
    property of it. The bytes' mtime is the property. When those two separate,
    something rewrote the roster and left the stamp describing a version that no
    longer exists — and everything downstream ages the queue against the stamp.

    It is reported rather than resolved, and resolving it is a judgement this
    program must not make: bumping the stamp asserts the queues below it were
    reviewed just now, which may well be false, and that assertion is the exact
    failure the task ledger was built to end.
    """
    if not ROSTER.exists():
        yield unchecked("roster stamp", f"{ROSTER.name} does not exist")
        return
    blob = _read(ROSTER)
    if blob is None:
        yield unchecked("roster stamp", f"{ROSTER.name} could not be read")
        return
    try:
        stamp = json.loads(blob).get("generated_at")
    except (ValueError, AttributeError):
        yield unchecked("roster stamp", f"{ROSTER.name} did not parse")
        return
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
        yield drift("roster stamp",
                    f"{ROSTER.name} has no usable generated_at, so nothing "
                    f"downstream can age its queues at all")
        return
    written = ROSTER.stat().st_mtime
    lag = written - stamp
    if lag > ROSTER_STAMP_LAG_S:
        yield drift("roster stamp",
                    f"{ROSTER.name} was written at {_clock(written)} but its "
                    f"generated_at still says {_clock(stamp)} — {_ago(lag)} "
                    f"behind the bytes",
                    ["the queues are aged against the stamp, so they are being "
                     "presented as older or newer than they are; decide "
                     "whether the stamp moves or the queue is re-declared"])


def check_roster_perms():
    """The roster and the ledger name who is working on what, including work
    that must not be disclosed. 0600 is asserted on every write by the code
    that writes them; this checks the result rather than the intention."""
    for path in (ROSTER, LEDGER):
        if not path.exists():
            continue
        try:
            mode = path.stat().st_mode & 0o777
        except OSError as exc:
            yield unchecked("log permissions",
                            f"{path.name}: {type(exc).__name__}")
            continue
        if mode != 0o600:
            yield drift("log permissions",
                        f"{path.name} is {oct(mode)}, not 0600",
                        ["it records who is working on what, by name"])


# --- CHECK 4: uncommitted work ------------------------------------------------

def check_uncommitted():
    """Work that exists only in the working tree.

    THERE IS NO REMOTE ON ANY OF THESE REPOS — re-checked here rather than
    assumed, because that sentence is itself a claim. So "uncommitted" does not
    mean "not pushed yet", it means the only copy is on one disk in one
    directory, and every commit made on 2026-08-03 was stranded at some point by
    a restart that killed the session holding it.

    MODIFIED TRACKED FILES ARE NAMED; UNTRACKED ENTRIES ARE COUNTED. An edit to
    a tracked file is work with a history it is diverging from, and knowing
    which file it is matters. Untracked entries are frequently scratch — render
    harnesses, screenshots — and listing eighteen of them every run is how a
    checker teaches people to skip its output. The count still appears, because
    a genuinely new source file hiding among the scratch is exactly what this
    should surface, and "seventeen untracked" is a number that changes when
    that happens.

    WHAT COUNTS AS DELIBERATE IS NOT DECIDED HERE, and that is not a dodge: the
    mechanism for "this is deliberately not in git" already exists and is
    .gitignore, which is itself version-controlled and reviewable. Anything
    genuinely scratch belongs there; anything else belongs in a commit. A
    hardcoded allow-list inside this file would be one more claim to go stale.
    """
    for repo in REPOS:
        if not (repo / ".git").exists():
            yield unchecked("uncommitted work",
                            f"{repo.name} is not a git repository")
            continue
        porcelain = _run(["git", "status", "--porcelain"], cwd=repo)
        if porcelain is None:
            yield unchecked("uncommitted work",
                            f"git status failed in {repo.name}")
            continue

        modified, untracked = [], []
        for line in porcelain.splitlines():
            if not line.strip():
                continue
            status, _, name = line[:2], line[2], line[3:]
            (untracked if status == "??" else modified).append(name.strip())

        if modified:
            yield drift("uncommitted work",
                        f"{repo.name}: {len(modified)} tracked file(s) changed "
                        f"and not committed",
                        [_names(modified),
                         "there is no remote on this repo, so this is the only "
                         "copy"])
        if untracked:
            yield drift("uncommitted work",
                        f"{repo.name}: {len(untracked)} untracked entr(ies) — "
                        f"commit them or put them in .gitignore",
                        [_names(untracked)])

        # A remote appearing would not be a fault, but it would quietly change
        # what "uncommitted" costs, and the paragraph above would stop being
        # true. Said out loud so the reasoning stays honest.
        remotes = _run(["git", "remote"], cwd=repo)
        if remotes is None:
            yield unchecked("uncommitted work",
                            f"could not list remotes in {repo.name}")
        elif remotes.strip():
            yield drift("uncommitted work",
                        f"{repo.name} now has a remote ({remotes.split()[0]}) — "
                        f"this file's reasoning about unrecoverable work is "
                        f"out of date and wants revisiting")


# --- CHECK 5: is each process running the source that is on disk? -------------

def check_process_versus_source():
    """For every unit: did the code change after the process started?

    THE GENERALISATION OF THE LEDGER FAILURE, and the answer to "did my change
    actually go live" without anyone having to remember to ask. A file edited at
    12:34 against a process started at 11:43 means that process is running the
    old code, and this exact confusion has cost hours here more than once.

    The comparison is the KERNEL'S start time for the pid against the mtime of
    the first-party sources that pid executes, both derived — see _pid_start and
    _first_party_sources, and read the second one's limits before trusting a
    silent pass on a unit whose real dependencies live elsewhere.

    Vendored trees and site-packages are deliberately not walked. whisper.cpp,
    kokoro-fastapi and ollama are checked on the mtime of the binary systemd
    actually executes, which is the thing that changes when they are rebuilt —
    Otto's Vulkan rebuild moved exactly that file.
    """
    props = _unit_properties()
    if props is None:
        yield unchecked("process vs source",
                        "systemctl did not answer, so no unit could be "
                        "compared against its source")
        return

    for unit in UNITS:
        info = props.get(unit)
        label = unit.replace(".service", "")
        if not info:
            yield unchecked("process vs source",
                            f"systemd did not report {unit}")
            continue
        if info.get("ActiveState") != "active":
            # Not a source-version question at all; the services check on the
            # board owns liveness. Saying it here too would be two alarms for
            # one fault.
            continue
        try:
            pid = int(info.get("MainPID", "0"))
        except ValueError:
            pid = 0
        if pid <= 0:
            yield unchecked("process vs source",
                            f"{label} is active but reports no MainPID")
            continue
        started = _pid_start(pid)
        if started is None:
            yield unchecked("process vs source",
                            f"{label}: the start time of pid {pid} could not be "
                            f"read from /proc")
            continue

        binary, argv = _exec_paths(info.get("ExecStart", ""))
        sources: set[Path] = set()
        if binary:
            sources.add(Path(binary))
        workdir = Path(info.get("WorkingDirectory") or ".")
        for arg in argv[1:]:
            if arg.endswith(".py"):
                entry = (workdir / arg) if not arg.startswith("/") else Path(arg)
                if entry.is_file():
                    sources |= _first_party_sources(entry)
                break

        if not sources:
            yield unchecked("process vs source",
                            f"{label}: no source file could be resolved from "
                            f"its ExecStart, so nothing was compared")
            continue

        newer = []
        for path in sorted(sources):
            try:
                changed = path.stat().st_mtime
            except OSError:
                continue                   # a vanished binary is the services
                                           # check's problem, not this one
            if changed > started:
                newer.append((path.name, changed))
        if newer:
            newer.sort(key=lambda x: -x[1])
            yield drift("process vs source",
                        f"{label} (pid {pid}) started at {_clock(started)} but "
                        f"{len(newer)} source file(s) changed after that — it "
                        f"is running old code",
                        [f"{name} changed at {_clock(when)}"
                         for name, when in newer[:MAX_NAMES]])


# --- CHECK 6: claims in documents that a command can falsify ------------------
#
# DELIBERATELY TINY, AND DELIBERATELY PARTIAL. Checking prose in general is not
# a thing that works; what works is picking the handful of sentences that (a) a
# person will act on and (b) a single command can prove false, and wiring only
# those. Everything else in the documentation stays a human's job.
#
# A claim whose text has VANISHED from its file is reported as a check that
# could not run, not as a pass. A verifier pointing at a sentence somebody
# deleted is a check that silently stopped working, which is the disease rather
# than the cure.


def check_loopback_claim():
    """Every service is on the side of the line it is supposed to be on.

    WHAT THIS USED TO DO, AND WHY IT WAS WORTH REPLACING. The old version read
    run-servers.sh's claim that "Everything binds to 127.0.0.1" and reported
    every voice-line socket that was not on loopback. That fired on the board
    and the client every single run — both of which bind 0.0.0.0 deliberately,
    because the Cloudflare tunnel cannot reach them otherwise. So the check
    nagged about correct behaviour, and a finding that is always present is one
    a person learns to scroll past. Meanwhile the thing that would actually
    matter — the brain leaving loopback — was only ever implied by the same
    line, and would have arrived looking exactly like the two false alarms
    beside it.

    WHAT IT DOES NOW. It asserts the split itself. Five services must be on
    loopback and two must not, and both directions are a finding:

      brain, local-brain, whisper, kokoro, voiceprint   MUST be loopback
      board, client                                     MUST NOT be

    The brain is the one that matters and the reason the rest are here with it:
    it holds full tool access to the vault, so a LAN binding hands the vault to
    every device on the wifi. The reverse case is quieter but real — a public
    service that drifts onto loopback does not fail loudly, it just serves the
    tunnel a 502 while looking healthy in ss(8).

    A unit in neither set is reported rather than assumed safe. A new service is
    exactly when somebody forgets to decide which side it belongs on.
    """
    text = _read(RUN_SERVERS)
    if text is None:
        yield unchecked("loopback split",
                        f"{RUN_SERVERS.name} could not be read")
        return
    if "LOOPBACK-ONLY BY DESIGN" not in text:
        yield unchecked("loopback split",
                        f"{RUN_SERVERS.name} no longer carries the "
                        f"'LOOPBACK-ONLY BY DESIGN' marker this check is "
                        f"anchored to — repoint the check or delete it")
        return

    out = _run(["ss", "-H", "-tlnp"])
    if out is None:
        yield unchecked("loopback split",
                        "ss did not answer, so listening sockets could not be "
                        "checked")
        return

    props = _unit_properties()
    if props is None:
        yield unchecked("loopback split",
                        "systemctl did not answer, so sockets could not be "
                        "attributed to units")
        return
    pids = {}
    for unit in UNITS:
        try:
            pid = int((props.get(unit) or {}).get("MainPID", "0"))
        except ValueError:
            continue
        if pid > 0:
            pids[pid] = unit.replace(".service", "")

    # Which side of the line each service belongs on. Mirrored by the
    # LOOPBACK-ONLY header in run-servers.sh; change both or neither.
    loopback_only = {
        "voiceline-brain", "voiceline-local-brain", "voiceline-whisper",
        "voiceline-kokoro", "voiceline-voiceprint", "ollama",
    }
    publicly_bound = {"voiceline-board", "voiceline-client"}

    escaped, withdrawn, unclassified = [], [], []
    for line in out.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        addr, _, port = fields[3].rpartition(":")
        if not addr:
            continue
        holders = [int(p) for p in re.findall(r"pid=(\d+)", line)]
        owner = next((pids[p] for p in holders if p in pids), None)
        if owner is None:
            continue
        on_loopback = (addr in ("127.0.0.1", "[::1]", "localhost")
                       or addr.startswith("127."))
        where = f"{owner} on {addr}:{port}"
        if owner in loopback_only:
            if not on_loopback:
                escaped.append(where)
        elif owner in publicly_bound:
            if on_loopback:
                withdrawn.append(where)
        else:
            unclassified.append(where)

    if escaped:
        yield drift("loopback split",
                    f"{len(escaped)} service(s) that must stay on loopback are "
                    f"listening on another address",
                    [_names(sorted(set(escaped))),
                     "the brain holds full tool access to the vault; off "
                     "loopback it is reachable by every device on the wifi"])

    if withdrawn:
        yield drift("loopback split",
                    f"{len(withdrawn)} publicly-served service(s) retreated to "
                    f"loopback, so the tunnel cannot reach them",
                    [_names(sorted(set(withdrawn))),
                     "these answer markdalton.com/ai; on loopback they serve "
                     "the tunnel a 502 while looking healthy in ss"])

    if unclassified:
        yield drift("loopback split",
                    f"{len(unclassified)} listening service(s) are on neither "
                    f"side of the loopback split",
                    [_names(sorted(set(unclassified))),
                     "decide whether it belongs on loopback and add it to the "
                     "set in check_loopback_claim, rather than leaving it "
                     "silently unasserted"])


def check_public_hostname():
    """The public health probe must name a hostname the tunnel actually serves.

    THE FAILURE THIS CLOSES, and it is the twin of check_loopback_claim above.
    That check caught a BINDING-ADDRESS claim going stale; this one is the case
    it did not have. On 2026-08-03 the public hostname `ai.markdalton.com` was
    retired and its DNS record removed, and for hours the health scripts, the
    rotation tooling and a page of vault notes went on naming it the live public
    address. A `curl` against it then fails at *resolution*, which reads exactly
    like the whole stack being down — and nothing on this box said the name had
    ceased to exist. Mark was the detector, again.

    HOW IT CHECKS WITHOUT TOUCHING THE NETWORK. The obvious version resolves the
    hostname and fetches it. This program does neither, ever — a name lookup or
    an HTTP call can hang, and a checker you hesitate to run beside a live voice
    line is a checker nobody runs. Instead it compares two files already on this
    disk: the public URL that `voiceline-status` probes, against the set of
    hostnames the cloudflared ingress actually serves. A probe host the tunnel
    has no rule for is a name that answers nothing, whatever DNS says — which is
    the exact shape of the miss. The cost of the no-network rule is stated
    plainly: a hostname that IS in the ingress but has lost its DNS record would
    still pass here. That narrower gap is a human's to catch; this closes the one
    that actually bit.

    Anchored like every doc check here: if the probe line is gone, or no
    cloudflared config is readable, it reports COULD NOT CHECK and never a pass.
    """
    status_text = _read(VOICELINE_STATUS)
    if status_text is None:
        yield unchecked("public hostname",
                        f"{VOICELINE_STATUS.name} could not be read, so the "
                        f"public probe was not checked")
        return

    # Every http(s) URL in the health script, minus the loopback origins — what
    # is left is what the script presents as the PUBLIC address.
    urls = re.findall(r"https?://([^/\s\"')]+)", status_text)
    public = [h for h in urls
              if h not in ("127.0.0.1", "localhost", "::1", "[::1]")
              and not h.startswith("127.")]
    if not public:
        yield unchecked("public hostname",
                        f"{VOICELINE_STATUS.name} names no non-loopback host, so "
                        f"the public-probe line this check anchors to is gone — "
                        f"repoint the check or delete it")
        return

    served = None
    source = None
    for path in CLOUDFLARED_CONFIGS:
        text = _read(path)
        if text is None:
            continue
        served = set(re.findall(r"^\s*-?\s*hostname:\s*([^\s#]+)", text,
                                re.MULTILINE))
        source = path
        break
    if served is None:
        yield unchecked("public hostname",
                        "no cloudflared config was readable at /etc/cloudflared "
                        "or ~/.cloudflared, so the served hostnames are unknown")
        return
    if not served:
        yield unchecked("public hostname",
                        f"no ingress hostnames were parsed out of {source}, so "
                        f"this check has lost its reference point")
        return

    for host in sorted(set(public)):
        # A probe host may carry a :port; the ingress names never do. Compare on
        # the bare host so markdalton.com:443 would still match markdalton.com.
        bare = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
        if host not in served and bare not in served:
            yield drift("public hostname",
                        f"{VOICELINE_STATUS.name} probes the public address "
                        f"{host!r}, but the tunnel serves "
                        f"{_names(sorted(served))}",
                        [f"a request to {host} reaches no ingress rule, so it "
                         f"answers nothing and reads as the whole stack being "
                         f"down — this is the 2026-08-03 ai.markdalton.com shape",
                         f"served hosts read from {source}"])


def check_no_raw_rest_deploy_import():
    """publish-due-post.py must never touch deploy-pages.py's raw REST path.

    THE CLAIM THIS REPLACES WAS FALSE, FOUND 2026-08-21. The script's own
    docstring used to read "It never imports deploy-pages.py and never
    will; a test greps this file to prove the string is absent." No such
    test existed anywhere in JARVIS or markdalton-site -- there is no
    pytest wiring in scheduled/ at all. A documented claim that is untrue
    is worse than no claim, because the next person trusts it without
    checking. This is that test, so the corrected docstring can point here
    honestly instead of at a grep that was never written.

    WHY THE UNDERLYING RULE MATTERS. deploy-pages.py's raw three-call REST
    mechanism is structurally unable to ship edge/_worker.js -- Wrangler
    bundles that file into an undocumented "_worker.bundle" multipart field
    outside the content-hashed asset manifest, and raw REST cannot
    reproduce that. On 2026-08-17 a deploy through that path silently
    stripped the live Pages Function four minutes after it shipped: every
    page still answered 200, and only a POST to /talk revealed the forms
    were dead. publish-due-post.py deploys unattended, daily -- reaching
    for that path here would repeat that outage with nobody watching.

    DOCSTRINGS ARE DELIBERATELY EXCLUDED. The file's own module docstring
    names "deploy-pages.py" three times, in prose explaining exactly why it
    is avoided -- a naive substring match on this file's own text fires on
    that prose immediately, which is precisely the kind of false alarm this
    whole check exists to avoid causing elsewhere. So this parses the file
    and looks for a real `import deploy_pages` / `from deploy_pages import`,
    or the literal string used as an actual argument (e.g. inside a
    subprocess call) -- never a bare Expr string that is a module,
    function or class docstring.
    """
    path = JARVIS / "scheduled" / "publish-due-post.py"
    text = _read(path)
    if text is None:
        yield unchecked("no raw-rest deploy", f"{path.name} could not be read")
        return
    try:
        tree = ast.parse(text)
    except SyntaxError:
        yield unchecked("no raw-rest deploy",
                        f"{path.name} could not be parsed")
        return

    docstrings = set()
    doc_holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if not isinstance(node, doc_holders) or not node.body:
            continue
        first = node.body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            docstrings.add(id(first.value))

    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
                a.name == "deploy_pages" for a in node.names):
            found = True
        elif isinstance(node, ast.ImportFrom) and node.module == "deploy_pages":
            found = True
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in docstrings
              and ("deploy-pages.py" in node.value
                   or node.value == "deploy_pages")):
            found = True
        if found:
            break

    if found:
        yield drift("no raw-rest deploy",
                    f"{path.name} now references deploy-pages.py outside "
                    f"its own docstring",
                    ["this script must only deploy through wrangler -- the "
                     "raw REST path cannot ship edge/_worker.js and "
                     "silently stripped the live Function on 2026-08-17"])


def check_board_refuses_caching():
    """Does every response the board sends still forbid being cached?

    THE FAILURE THIS CLOSES, and it is a near miss rather than an outage. On
    2026-08-05 a report went round that Cloudflare was caching the gated feeds.
    Measured, it was not: cf-cache-status came back DYNAMIC on /ai/links,
    /ai/state, /ai/questions, /ai/status, /ai/metrics, /ai/dashboard and /ai,
    with and without a credential. But the REASON it was not caching turned out
    to rest almost entirely on one line in server.py — the origin says no-store,
    and Cloudflare honours that. Nothing at the edge was enforcing it, and the
    Cloudflare credential on this box (an Argo tunnel token, dns_records only)
    cannot read the zone's cache rules to find out whether anything ever would.

    So the property is real and it is one edit deep. Delete a header from _send
    and the feeds keep working perfectly, the gate keeps refusing strangers, the
    board looks identical — and a shared cache somewhere starts holding a copy of
    /links, which is a list of Google Drive URLs, each one a bearer capability.
    There is no log of that, anywhere, because the request never reaches this box.
    A silent loss of a safety property is exactly what this program is for.

    WHY IT CHECKS THE SOURCE AND NOT THE WIRE. Same rule as check_public_hostname:
    this program makes no network call, ever, because a checker you hesitate to
    run beside a live voice line is a checker nobody runs. The cost is named
    plainly — a running process whose source still has the header but which was
    started before it was added would pass here. That gap is already covered:
    check_process_versus_source catches a process older than its source.

    TWO QUESTIONS, because they fail independently:
      1. Does _send still send the directives? Losing "no-store" is the whole
         failure. The others are defence in depth and are reported separately so
         a partial loss does not read the same as a total one.
      2. Is _send still the ONLY way a response leaves? The headers are set at
         one funnel on purpose. A second send_response() call site anywhere in
         that file is a route that answers without any of this, and it would be
         invisible — a new endpoint works first time and simply is not covered.
    """
    text = _read(BOARD_SOURCE)
    if text is None:
        yield unchecked("board caching",
                        f"{BOARD_SOURCE.name} could not be read, so whether the "
                        f"board still refuses caching is unknown")
        return

    match = re.search(r"def _send\(.*?\n(.*?)\n    def ", text, re.DOTALL)
    if match is None:
        yield unchecked("board caching",
                        f"the _send method was not found in {BOARD_SOURCE.name}; "
                        f"this check has lost its reference point — repoint it or "
                        f"delete it, but do not leave it silently passing")
        return
    body = match.group(1)

    # Comments in this file discuss these headers at length, so the check has to
    # look at code rather than at prose or it will pass on the strength of a
    # paragraph explaining why the header used to be there.
    code = "\n".join(line.split("#", 1)[0] for line in body.splitlines())

    sent = {}
    for name, value in re.findall(
            r"""send_header\(\s*["']([^"']+)["']\s*,\s*\n?\s*["']([^"']*)["']""",
            code):
        sent[name.lower()] = value.lower()
    cache_control = sent.get("cache-control", "")

    if "no-store" not in cache_control:
        yield drift("board caching",
                    "the board's _send NO LONGER SENDS Cache-Control: no-store — "
                    "every response it makes is now cacheable by anything in "
                    "front of it",
                    [f"Cache-Control is currently {cache_control!r}",
                     "/links is a list of Google Drive URLs and each one is a "
                     "bearer capability; /status names every unit and pid",
                     "a cached copy is served without ever reaching the gate, so "
                     "board-gate.log will show nothing at all",
                     f"read from {BOARD_SOURCE}"])
    else:
        weakened = [label for label, present in (
            ("private in Cache-Control", "private" in cache_control),
            ("CDN-Cache-Control", "no-store" in sent.get("cdn-cache-control", "")),
            ("Vary: Cookie", "cookie" in sent.get("vary", "")),
        ) if not present]
        if weakened:
            yield drift("board caching",
                        f"no-store is still sent, but the defence in depth added "
                        f"on 2026-08-05 has been reduced: {_names(weakened)} "
                        f"{'is' if len(weakened) == 1 else 'are'} gone",
                        ["Cache-Control is the LOWEST-priority cache header a CDN "
                         "reads — Cloudflare's order is Cache Response Rules > "
                         "Cloudflare-CDN-Cache-Control > CDN-Cache-Control > "
                         "Cache-Control",
                         "this is not yet a leak; it is the margin that stops one "
                         "edit from becoming one"])

    # One funnel, or it is not a funnel. Counted on code, not on comments.
    stripped = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    call_sites = len(re.findall(r"self\.send_response\s*\(", stripped))
    if call_sites != 1:
        yield drift("board caching",
                    f"{BOARD_SOURCE.name} has {call_sites} send_response() call "
                    f"sites; the cache headers are set at exactly one of them",
                    ["every response is supposed to leave through _send so it "
                     "cannot be added to this server without being covered",
                     "a second call site is a route that answers with no "
                     "Cache-Control at all, and it will work perfectly while "
                     "doing it"])


# --- CHECK 7: this program's own assumptions ----------------------------------

def check_threshold_matches_board():
    """Does STALE_AFTER_S still match the board's TEAM_LEDGER_STALE_AFTER?

    A checker carrying its own copy of somebody else's constant is precisely
    the failure this whole file is about. Rather than pretend the duplication
    is not there, the duplication is CHECKED: the real value is read out of the
    board's source, and a disagreement is reported like any other drift.

    The value is read by pattern rather than by importing server.py, because
    importing it executes module-level code in a process that has no business
    running the board's startup — and a checker that imports a live service's
    source to audit it is one refactor away from doing something.
    """
    text = _read(BOARD_SOURCE)
    if text is None:
        yield unchecked("stale threshold",
                        f"{BOARD_SOURCE.name} could not be read")
        return
    match = re.search(r"^TEAM_LEDGER_STALE_AFTER\s*=\s*(.+)$", text, re.MULTILINE)
    if match is None:
        yield unchecked("stale threshold",
                        "TEAM_LEDGER_STALE_AFTER was not found in "
                        f"{BOARD_SOURCE.name}; this check has lost its "
                        f"reference point")
        return
    expression = match.group(1).split("#")[0].strip()
    if not re.fullmatch(r"[\d\s*+]+", expression):
        yield unchecked("stale threshold",
                        f"TEAM_LEDGER_STALE_AFTER is {expression!r}, which this "
                        f"check will not evaluate")
        return
    try:
        value = eval(expression, {"__builtins__": {}}, {})   # digits and * + only
    except Exception:
        yield unchecked("stale threshold",
                        f"TEAM_LEDGER_STALE_AFTER ({expression!r}) did not "
                        f"evaluate")
        return
    if value != STALE_AFTER_S:
        yield drift("stale threshold",
                    f"this checker ages open dispatches at {STALE_AFTER_S}s but "
                    f"the board uses {value}s — the two disagree about when a "
                    f"specialist stops counting as working")


def check_unit_list_matches_board():
    """Does the unit list above still match the board's SERVICES tuple?

    UNITS is the one hardcoded table in this file, because systemd cannot be
    asked which units belong to the voice line. A hardcoded table is a claim, so
    it gets checked against the other place the same list is written down. A
    ninth service added in one and not the other is reported rather than
    discovered when a check silently stops covering it.
    """
    text = _read(BOARD_SOURCE)
    if text is None:
        yield unchecked("unit list", f"{BOARD_SOURCE.name} could not be read")
        return
    block = re.search(r"^SERVICES[^=]*=\s*\((.*?)^\)", text,
                      re.MULTILINE | re.DOTALL)
    if block is None:
        yield unchecked("unit list",
                        f"the SERVICES tuple was not found in "
                        f"{BOARD_SOURCE.name}; this check has lost its "
                        f"reference point")
        return
    theirs = set(re.findall(r'"([\w.-]+\.service)"', block.group(1)))
    if not theirs:
        yield unchecked("unit list",
                        "no unit names were found inside the board's SERVICES "
                        "tuple")
        return
    mine = set(UNITS)
    for missing in sorted(theirs - mine):
        yield drift("unit list",
                    f"the board watches {missing} and this checker does not — "
                    f"every check here silently skips it")
    for extra in sorted(mine - theirs):
        yield drift("unit list",
                    f"this checker watches {extra} and the board does not")


# --- The runner ---------------------------------------------------------------

def check_offline_gate():
    """Is the offline gate still wired, still loadable, and still firing?

    WHY A CHECK AND NOT A TEST. The gate at hooks/offline-gate.py is what stops a
    change taking Mark off the air, and it is loaded from a single untracked-until
    -tonight JSON file by a process that reads it once. Every way it can die is
    silent: settings.json stops parsing and the CLI ignores the whole file
    without a word (documented behaviour in print/SDK mode); the script stops
    compiling and the harness fails OPEN, measured, so every command sails
    through; someone deletes the matcher. In all three cases the box looks
    exactly like a week where nothing risky was attempted.

    So this asks three separate questions, because they fail independently:
    is it declared, can it run, and has it actually run.

    THE THIRD ONE IS THE ONE THAT MATTERS and it is why the gate touches a stamp
    file on every single invocation. Declared-and-broken is the state that reads
    as safe. The comparison is against the newest transcript in this project —
    if a session has been working for the last hour and the gate has not run
    once in that time, it is wired to nothing.

    ITS FALSE POSITIVE IS NAMED RATHER THAN ENGINEERED AWAY: the matcher covers
    Bash, Write and Edit only, so an hour of pure reading and thinking legitimately
    never fires it. That is why the window is an hour rather than five minutes,
    and why this says "has not fired" rather than "is broken".
    """
    settings = JARVIS / ".claude" / "settings.json"
    gate = JARVIS / "hooks" / "offline-gate.py"

    blob = _read(settings)
    if blob is None:
        yield unchecked("offline gate", f"{settings} could not be read")
        return
    try:
        config = json.loads(blob)
    except ValueError as exc:
        yield drift("offline gate",
                    f"{settings.name} IS NOT VALID JSON ({str(exc)[:80]}), so "
                    f"EVERY hook in it is inactive for new sessions",
                    ["nothing announces this — the CLI ignores a settings file "
                     "that fails validation and carries on",
                     "the request logger, the boot report, the job watchdog and "
                     "the offline gate are all in that file"])
        return

    declared = [entry
                for group in (config.get("hooks") or {}).get("PreToolUse") or []
                for entry in group.get("hooks") or []
                if "offline-gate.py" in (entry.get("command") or "")]
    if not declared:
        yield drift("offline gate",
                    "no PreToolUse hook in settings.json runs offline-gate.py — "
                    "nothing is checking whether a change takes Mark offline",
                    ["this is the check Mark asked for on 2026-08-04 after being "
                     "cut off seventeen times in forty-eight hours"])
        return
    if any("timeout" not in entry for entry in declared):
        yield drift("offline gate",
                    "the gate is wired with no explicit timeout, so the harness "
                    "default of 600s applies and a hung gate stalls every Bash "
                    "call for ten minutes")

    source = _read(gate)
    if source is None:
        yield drift("offline gate",
                    f"settings.json runs {gate} and that file cannot be read")
        return
    try:
        compile(source, str(gate), "exec")
    except SyntaxError as exc:
        yield drift("offline gate",
                    f"{gate.name} does not compile (line {exc.lineno}: {exc.msg})",
                    ["a hook that crashes FAILS OPEN — measured on this box — so "
                     "every command is currently running unchecked"])
        return

    stamp = LOGS / ".offline-gate-stamp"
    if not stamp.exists():
        yield drift("offline gate",
                    "the gate has never run — its stamp file does not exist",
                    [f"expected at {stamp}",
                     "wired but never invoked usually means the session "
                     "predates the wiring, or the matcher does not match"])
        return

    transcripts = HOME / ".claude" / "projects" / "-home-mdalton-Documents-JARVIS"
    try:
        newest = max((p.stat().st_mtime for p in transcripts.glob("*.jsonl")),
                     default=None)
    except OSError:
        newest = None
    if newest is None:
        yield unchecked("offline gate",
                        "the gate is wired and compiles, but whether it has FIRED "
                        "could not be determined — no session transcript to "
                        "compare its stamp against")
        return

    lag = newest - stamp.stat().st_mtime
    if lag > 60 * 60:
        yield drift("offline gate",
                    f"the gate is wired and compiles but has not fired in "
                    f"{_ago(lag)} of session activity",
                    [f"last fired {_clock(stamp.stat().st_mtime)}, last session "
                     f"activity {_clock(newest)}",
                     "a long read-only stretch can do this legitimately; a "
                     "matcher that no longer matches cannot be told apart from "
                     "it without looking"])


def check_site_assets_exist():
    """Every image, stylesheet and download the public site links to is on disk.

    MARK FOUND THIS ONE AND ASKED WHY THE CHECKER DID NOT — 2026-08-12, the
    broken images on /visualizers. He was right to ask; nothing here was looking.

    THE TRAP IS THAT A MISSING ASSET RETURNS 200. An unmapped path on that host
    falls through to the marketing page, so `curl -o /dev/null -w %{http_code}`
    reports 200 for a deleted PNG and the browser gets HTML where an image
    should be. Every deploy today was verified by status code and every one of
    them passed while the image was broken. Checking the CONTENT TYPE is the
    difference — or, as here, checking the file exists before it ever ships.

    IT READS THE TREE, NOT THE NETWORK. No requests, no timeouts, nothing that
    can fail for a reason unrelated to the question, and it works with the site
    unreachable. The specific failure it would have caught: the file existed
    only in `.build-live/`, which is excluded from deploys, so the page shipped
    without it every single time.

    Absolute and relative hrefs both, because the page that broke used relative.
    """
    if not SITE.is_dir():
        yield unchecked("site assets", f"{SITE} is not readable")
        return

    pages = sorted(SITE.glob("*.html")) + sorted((SITE / "blog").glob("*.html"))
    if not pages:
        yield unchecked("site assets", "no pages found to check")
        return

    missing: dict[str, list[str]] = {}
    for page in pages:
        try:
            html = page.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for ref in re.findall(r'(?:src|href|poster|data-prompt)="(/?assets/[^"?#]+)"',
                              html):
            if not (SITE / ref.lstrip("/")).is_file():
                missing.setdefault(ref, []).append(page.name)

    for ref, on in sorted(missing.items()):
        yield drift("site assets",
                    f"{ref} is linked by {len(on)} page(s) and is not in the "
                    f"deploy tree",
                    [f"first on {on[0]}",
                     "a missing asset answers 200 with the marketing page, so "
                     "the browser shows a broken image and a status check passes"])


_HASHED_ASSET = re.compile(r"\.[0-9a-f]{8}\.css$")
_CACHEFIX = re.compile(
    r'<link[^>]+href="(/assets/[^"?#]+\.css)(?:\?cachefix=(\d{8}))?"')


def check_stylesheet_cache_busting():
    """A changed stylesheet is served under a name every cache already has.

    MARK FOUND THIS ONE, AND HE FOUND IT AFTER I HAD JUST TOLD HIM THE SITE WAS
    FINE — 2026-08-19: "then you didn't do it right.. just an example only the
    header matches here but thte body to does not". He sent a screenshot of
    /blog. The header was correct and the body was flat black.

    THE SITE WAS CORRECT. HIS COPY WAS NOT, and that distinction is the whole
    check. Rendering the same live URL with a cold cache produced the particle
    field and the bracketed eyebrow; his browser was four hours into a
    `max-age=14400` on a stylesheet whose filename had not changed.

    WHY THE HEADER SURVIVED AND THE BODY DID NOT — this is the tell, and it is
    worth recognising on sight. The nav is styled by `site.cc17860c.css`, whose
    name carries a content hash, so a change to it produces a NEW url and every
    cache misses. The hero field lives in `blog-learn-theme.css`, whose name has
    never changed once. Same deploy, same page, two stylesheets, and only one of
    them reached him. A half-styled page is the signature of exactly this.

    `palette.css` was worse, because it looked handled: it carried
    `?cachefix=20260814` while the file itself had been rewritten on 20260819.
    A cache-busting token that is edited by hand is a token somebody eventually
    forgets, and a stale one is indistinguishable from a fresh one by eye. That
    is what this function is for — nobody has to remember, because it is checked.

    IT READS THE TREE, NOT THE NETWORK, so it works with the site unreachable
    and cannot fail for a reason unrelated to the question.
    """
    if not SITE.is_dir():
        yield unchecked("stylesheet cache", f"{SITE} is not readable")
        return

    # blog/ IS INCLUDED, AND LEAVING IT OUT ALREADY COST SOMETHING — the first
    # version of this check globbed only "*.html" and reported clean while all
    # 22 posts linked palette.css and blog-learn-theme.css with no token at all.
    # The posts are the most-shared pages on the site. Same glob as
    # check_site_assets_exist, which had this right from the start.
    pages = sorted(SITE.glob("*.html")) + sorted((SITE / "blog").glob("*.html"))
    if not pages:
        yield unchecked("stylesheet cache", "no pages found to check")
        return

    def content_date(path: Path) -> str | None:
        """The day this file's CONTENT last changed, YYYYMMDD.

        git first, because mtime moves on a checkout that changed nothing and
        would raise a false alarm every time a branch is switched. mtime is the
        fallback for a file that is not committed yet, which is the normal state
        of a stylesheet being worked on right now.
        """
        out = _run(["git", "log", "-1", "--format=%ad",
                    "--date=format:%Y%m%d", "--",
                    str(path.relative_to(SITE))], cwd=SITE)
        if out:
            return out.strip()
        try:
            return time.strftime("%Y%m%d", time.localtime(path.stat().st_mtime))
        except OSError:
            return None

    stale: dict[str, tuple[str, str, list[str]]] = {}
    unversioned: dict[str, list[str]] = {}
    unreadable: set[str] = set()

    for page in pages:
        try:
            html = page.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for ref, token in _CACHEFIX.findall(html):
            # A content hash in the filename IS the cache busting, and it is the
            # stronger form — it cannot go stale because it is derived. Nothing
            # to check.
            if _HASHED_ASSET.search(ref):
                continue
            path = SITE / ref.lstrip("/")
            if not path.is_file():
                # check_site_assets_exist already reports a missing asset; do not
                # report the same fault twice under a second name.
                continue
            changed = content_date(path)
            if changed is None:
                unreadable.add(ref)
                continue
            if not token:
                unversioned.setdefault(ref, []).append(page.name)
            elif token < changed:
                _, _, on = stale.setdefault(ref, (token, changed, []))
                on.append(page.name)

    for ref, on in sorted(unversioned.items()):
        yield drift("stylesheet cache",
                    f"{ref} is linked with NO cache-busting by {len(on)} page(s) "
                    f"and its name has no content hash",
                    [f"first on {on[0]}",
                     "it is served with max-age=14400, so a returning visitor "
                     "gets the previous version for up to four hours after any "
                     "change to it",
                     "the page's other stylesheets are content-hashed and do "
                     "bust, which is what produces a half-styled page rather "
                     "than an obviously broken one"])

    for ref, (token, changed, on) in sorted(stale.items()):
        yield drift("stylesheet cache",
                    f"{ref} last changed {changed} and is still linked as "
                    f"?cachefix={token} by {len(on)} page(s)",
                    [f"first on {on[0]}",
                     "the token is what tells every cache the file is new, so "
                     "until it is bumped the change does not reach anyone who "
                     "has been to the site recently"])

    for ref in sorted(unreadable):
        yield unchecked("stylesheet cache",
                        f"could not determine when {ref} last changed, so "
                        f"whether its cache token is current is unknown")


def check_site_links_resolve():
    """Every link the public pages carry actually answers, on the right host.

    MARK FOUND THIS ONE TOO — 2026-08-12: "this link is dead
    https://ai.markdalton.com/agents fix it ane make sure we are continue to
    look". The second half is this function.

    THE FAULT WAS A RELATIVE LINK CROSSING A HOST. The site lives on two:
    markdalton.com carries /agents, /team, /blog and the rest, and
    ai.markdalton.com carries /learn and /talk. A footer written with `/agents`
    is correct on one and points at nothing on the other, and it was shipped
    onto both. The nav has known this since 2026-08-06 and says so in its own
    comment; the footer was written a week later and did not.

    SO IT CHECKS THE PAGE WHERE IT IS SERVED, not just the file. A link is only
    wrong in context — `/agents` is fine in markdalton.com's copy of a page and
    dead in ai.markdalton.com's. Relative links on the two ai-hosted pages are
    resolved against that host, which is what makes the fault visible.

    NETWORK, AND THEREFORE ALLOWED TO BE UNAVAILABLE. Anything that cannot be
    reached is reported as could-not-check rather than as drift — a checker that
    cries about the wifi is one that gets ignored, and being ignored is how the
    real thing hides.
    """
    if not SITE.is_dir():
        yield unchecked("site links", f"{SITE} is not readable")
        return

    # The two ai-hosted pages, and everything else on the apex. Kept as data
    # because it is exactly the fact the footer got wrong.
    ai_pages = {"learn.html", "talk.html"}

    targets: dict[str, list[str]] = {}
    for page in sorted(SITE.glob("*.html")):
        try:
            html = page.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        host = ("https://ai.markdalton.com" if page.name in ai_pages
                else "https://markdalton.com")
        for href in re.findall(r'href="([^"#?]+)"', html):
            if href.startswith("http"):
                url = href
            elif href.startswith("/"):
                url = host + href
            else:
                continue
            if "markdalton.com" not in url:
                continue
            targets.setdefault(url, []).append(page.name)

    if not targets:
        yield unchecked("site links", "no links found to check")
        return

    # CONCURRENT, BECAUSE THE STARTUP CHECK HAS TO STAY CHEAP. Run one at a
    # time this took long enough to blow a two-minute timeout on its first
    # outing — and a check nobody can afford to run is a check that does not
    # exist. Eight at once with an eight-second ceiling each keeps the whole
    # thing inside a couple of seconds.
    # A DEAD LINK ONLY MATTERS IF THE PAGE CARRYING IT IS LIVE — added
    # 2026-08-23. Before this, the check globbed every local .html and tested
    # its links against production, so a page that had been WRITTEN but never
    # DEPLOYED reported as three broken links on the live site. That is what
    # `os.html` and `work.html` did tonight: drafts from that afternoon, linking
    # to each other and to a `/personal` page nobody has written yet. Nothing on
    # the live site was broken.
    #
    # NOT HIDDEN — COUNTED AND SAID. The skipped ones are reported as a
    # could-not-check line with the page names in it, because "I ignored these"
    # is a different claim from "these are fine" and a checker that blurs the
    # two is worth nothing.
    page_urls: dict[str, str] = {}
    for page in sorted(SITE.glob("*.html")):
        host = ("https://ai.markdalton.com" if page.name in ai_pages
                else "https://markdalton.com")
        stem = "" if page.stem == "index" else "/" + page.stem
        page_urls[page.name] = host + (stem or "/")

    from concurrent.futures import ThreadPoolExecutor
    urls = sorted(targets)
    probe = sorted(set(urls) | set(page_urls.values()))
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = dict(zip(probe, pool.map(_http_status, probe)))

    def _page_is_live(name: str) -> bool:
        code = codes.get(page_urls.get(name, ""))
        return code is not None and code < 400

    unreachable = 0
    draft_links: list[str] = []
    for url in urls:
        code = codes.get(url)
        if code is None:
            unreachable += 1
            continue
        if code >= 400:
            pages = sorted(set(targets[url]))
            live_pages = [p for p in pages if _page_is_live(p)]
            if not live_pages:
                draft_links.append(f"{url} (from {', '.join(pages[:2])})")
                continue
            yield drift("site links",
                        f"{url} answers {code}",
                        [f"linked from {', '.join(live_pages[:3])}"
                         + (f" and {len(live_pages) - 3} more"
                            if len(live_pages) > 3 else ""),
                         "a link that crosses between markdalton.com and "
                         "ai.markdalton.com has to be absolute — the two hosts "
                         "do not carry the same pages"])

    if draft_links:
        yield unchecked("site links",
                        f"{len(draft_links)} dead link(s) live only in pages that "
                        f"are not deployed — drafts, not site faults: "
                        + "; ".join(draft_links[:4]))

    if unreachable:
        yield unchecked("site links",
                        f"{unreachable} of {len(targets)} link(s) could not be "
                        f"reached at all — probably no network, not a dead link")


def _http_status(url: str):
    """The status code, or None if the request could not be made at all.

    None and 404 are DIFFERENT ANSWERS and conflating them is the whole risk
    here: one means the link is broken, the other means this box is offline.
    """
    import urllib.error
    import urllib.request

    # HEAD FIRST, GET AS A FALLBACK — and the fallback is not optional. The
    # board on ai.markdalton.com answers 501 to HEAD because it does not
    # implement the verb; the same URL answers 303 to a GET, which is a working
    # redirect to the login. Reporting that as a dead link was this check's
    # first false positive, caught on its first run, and a checker whose opening
    # act is a wrong accusation is one nobody reads again.
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method,
                                     headers={"User-Agent": "jarvis-drift-check"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return r.status
        except urllib.error.HTTPError as exc:
            # 501/405 mean "not that verb", never "not that page".
            if exc.code in (405, 501) and method == "HEAD":
                continue
            return exc.code
        except Exception:
            return None
    return None


# --- CHECK 8: bare HTTP requests at this box's own WAF-fronted hosts ----------
#
# THE FAULT, FOUND FOUR TIMES IN TWO WEEKS. Cloudflare's WAF blocks the
# literal default `Python-urllib/3.x` User-Agent string with a 403 (error
# 1010), unconditionally, before the request reaches markdalton.com or any
# *.pages.dev deployment at all -- it is not a timing problem, so no amount
# of retrying fixes it. `edge/verify-deploy.py` hit and fixed it 2026-08-06;
# `scheduled/publish-due-post.py`, `scheduled/publish-pause-post.py` and
# `edge/deploy-production.py` each independently reintroduced it, unnoticed,
# until a genuinely-live blog post was reported dead for three straight
# days. Full account: ~/Documents/Bram/2026-08-21 blog-publish verify()
# false-failure fix.md.
#
# FILE-SCOPED, NOT CALL-SITE SCOPED, AND THAT LIMIT IS DELIBERATE. Tying a
# User-Agent to the exact call that needs one would mean tracing which
# `Request(...)` a given `headers=` argument reaches THROUGH a shared helper
# -- this codebase already writes `get()` / `http()` wrappers that take a
# bare `url` argument for exactly this purpose, and the header lives in the
# wrapper's definition, not at every call site. Real call-graph tracing is
# not a proportionate check. Instead: does this file make an outbound
# urllib call, does it reference one of our own fronted hosts anywhere, and
# does it never once say "User-Agent" anywhere in its own text? All three
# true is the exact shape of every one of the four real occurrences, and
# none of them was true of any file after it was fixed -- fixing this bug
# always leaves the string "User-Agent" somewhere in the file.
#
# THE COST OF THAT LOOSENESS, SAID PLAINLY: a file that talks to a fronted
# host safely from one function and unsafely from another would read as
# clean. THE COST OF TIGHTENING IT WOULD BE WORSE: a check that cries wolf
# even once here gets ignored, which is the same way this fault happened in
# the first place -- see Mark's own reasoning for choosing this over a
# write-time gate, 2026-08-21.
#
# ONLY FIRST-PARTY FILES, ONLY OUR OWN HOSTS. `git ls-files` is the
# boundary, same as check_uncommitted -- it already excludes vendored trees
# and venvs without a second allow-list to maintain. Google's APIs, the
# Cloudflare management API and ollama on loopback do not sit behind this
# WAF and are deliberately not in FRONTED_HOSTS; flagging them would be
# exactly the false alarm this check exists to avoid, and Mark checked by
# hand tonight that none of them WAF-block.

FRONTED_HOSTS = ("markdalton.com", ".pages.dev")

_HTTP_CALL_RE = re.compile(r"\burlopen\s*\(|\bRequest\s*\(")
_URLLIB_IMPORT_RE = re.compile(
    r"^\s*(import\s+urllib\.request|from\s+urllib\.request\s+import)",
    re.MULTILINE)
# A URL, not a bare domain. THE FIRST VERSION OF THIS CHECK matched the bare
# string "markdalton.com" anywhere in the file and cried wolf on its first
# real run, 2026-08-21 -- six files flagged, every one of them innocent:
# `jarvis@markdalton.com` / `mark@markdalton.com` as an email address, and
# WORKSPACE_DOMAIN = "markdalton.com" used to impersonate a Google Workspace
# subject, never as an HTTP target. None of the six ever builds a URL out of
# it. Requiring the scheme prefix is what tells a request apart from an
# address -- proven against those exact six before this shipped.
_URL_RE = re.compile(r"https?://[\w.:-]+")


def _mentions_fronted(node, fronted_names: set) -> bool:
    """Does this expression evaluate to a URL at one of our fronted hosts?

    Resolves the three shapes that actually occur here: a literal, a name
    bound to a literal, and either of those inside an f-string or a `+`
    concatenation. Anything cleverer is a call graph, and the block comment
    above is right that a call graph is not a proportionate check.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if any(h in sub.value for h in FRONTED_HOSTS) and "://" in sub.value:
                return True
        elif isinstance(sub, ast.Name) and sub.id in fronted_names:
            return True
    return False


def _fronted_target_reached(text: str) -> bool:
    """True if some urlopen/Request call is actually AIMED at a fronted host.

    THIS IS THE 2026-08-23 TIGHTENING, and it is the SECOND time this check has
    had to be narrowed for the same reason. The first version matched a bare
    domain and flagged six innocent files. This version matched any URL with a
    scheme anywhere in the file -- and tonight it flagged four more, every one
    of them clean:

      jarvis-voice-check.py / wren-aurelia-centering-harness.py -- hold
        `https://ai.markdalton.com/` as a constant they hand to a BROWSER, while
        their only urllib calls go to 127.0.0.1 CDP.
      oauth_google.py -- holds the fronted address as an OAuth redirect URI,
        which is given to Google and never fetched.
      google_search_console.py -- mentions it in a comment and inside an error
        message explaining what a Search Console property looks like.

    The check's own comment says "a check that cries wolf even once here gets
    ignored". It had cried wolf four times, so by its own standard it needed
    this.

    WHAT IS TRADED AWAY, said as plainly as the comment above says its own
    tradeoff: a file whose request helper takes a bare `url` parameter, with the
    fronted URL supplied by a CALLER in another file, no longer matches. That is
    a real gap. It is accepted because all four genuine occurrences were direct
    -- `urlopen(f"{SITE}/blog/...")` with SITE a fronted literal in the same
    file -- and because a checker nobody reads catches nothing at all.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Cannot parse, so cannot narrow. Fall back to the older, looser
        # behaviour rather than silently calling the file clean.
        return True

    fronted_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if _mentions_fronted(node.value, set()):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        fronted_names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name) and _mentions_fronted(node.value, set()):
                fronted_names.add(node.target.id)

    # A second pass, so `A = "https://markdalton.com"` then `B = A + "/x"`
    # resolves too.
    for _ in range(3):
        before = len(fronted_names)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and _mentions_fronted(node.value, fronted_names):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        fronted_names.add(target.id)
        if len(fronted_names) == before:
            break

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (
            fn.id if isinstance(fn, ast.Name) else "")
        if name not in ("urlopen", "Request"):
            continue
        args = list(node.args) + [kw.value for kw in node.keywords
                                  if kw.arg in (None, "url", "fullurl")]
        for arg in args:
            if _mentions_fronted(arg, fronted_names):
                return True
    return False


def _bare_fronted_http(text: str) -> bool:
    """True if a file's own text has the exact shape of the fault above.

    Pure text logic, no filesystem or git -- kept separate from the check
    below so it can be proven against a planted example without touching
    any real repo, the same way the fix itself was proven tonight.
    """
    if not _URLLIB_IMPORT_RE.search(text):
        return False
    if not _HTTP_CALL_RE.search(text):
        return False
    urls = _URL_RE.findall(text)
    if not any(host in url for host in FRONTED_HOSTS for url in urls):
        return False
    if "user-agent" in text.lower():
        return False
    return _fronted_target_reached(text)


def check_bare_fronted_http():
    """Every first-party urllib call at markdalton.com/*.pages.dev carries a
    User-Agent. See the block comment above for why this is file-scoped and
    for the four times getting this wrong has already cost real days.
    """
    for repo in REPOS:
        if not (repo / ".git").exists():
            yield unchecked("fronted http",
                            f"{repo.name} is not a git repository")
            continue
        listed = _run(["git", "ls-files", "*.py"], cwd=repo)
        if listed is None:
            yield unchecked("fronted http",
                            f"git ls-files failed in {repo.name}, so its "
                            f"Python files were not scanned")
            continue
        for rel in listed.splitlines():
            rel = rel.strip()
            if not rel:
                continue
            path = repo / rel
            text = _read(path)
            if text is None:
                yield unchecked("fronted http",
                                f"{repo.name}/{rel} could not be read")
                continue
            if _bare_fronted_http(text):
                matched = ", ".join(h for h in FRONTED_HOSTS if h in text)
                yield drift("fronted http",
                            f"{repo.name}/{rel} calls urllib against a "
                            f"WAF-fronted host with no User-Agent anywhere "
                            f"in the file",
                            [f"host(s) matched: {matched}",
                             "Cloudflare 403s Python-urllib's default UA "
                             "unconditionally -- this will fail every "
                             "attempt, not intermittently, and will not be "
                             "fixed by retrying"])


def check_post_is_listed():
    """A published blog post is reachable from the blog page.

    JARVIS DID THIS ON 2026-08-28 AND MARK DID NOT HAVE TO FIND IT ONLY BECAUSE
    HE ASKED A DIFFERENT QUESTION. A post was written, given a schedule entry,
    and deployed. It answered 200 at its own address for about fifteen minutes
    and appeared nowhere on /blog, because `blog.html` is HAND-MAINTAINED and
    nothing regenerates it. There is a comment directly above the card that was
    edited saying this had happened before: PUBLISHED AND LISTED ARE TWO
    DIFFERENT THINGS, and only one of them was happening.

    THE SHAPE OF THE FAULT IS THE POINT, not the blog. It is a job with three
    parts where two were done — write the file, add the schedule row, link it —
    and nothing anywhere could tell that the third was missing. That class of
    miss is what this check exists to end, and the same shape is why the second
    check below exists.

    Reads the tree. No network, nothing that can fail for an unrelated reason.
    """
    blog_dir = SITE / "blog"
    listing = SITE / "blog.html"
    schedule = Path.home() / "Documents/JARVIS/scheduled/blog-schedule.json"
    if not blog_dir.is_dir() or not listing.is_file():
        yield unchecked("post is listed", f"{blog_dir} or {listing} is not readable")
        return
    try:
        listed = set(re.findall(r'href="/blog/([a-z0-9-]+)"', listing.read_text(encoding="utf-8")))
        rows = json.loads(schedule.read_text(encoding="utf-8"))
    except Exception as exc:
        yield unchecked("post is listed", f"could not read the listing or schedule: {exc}")
        return

    # DUE, not merely scheduled. The first version of this check flagged every
    # post dated into September and was wrong about all of them -- the gate
    # holds those back on purpose, so unlisted is the correct state for them.
    # A checker that cries wolf is one people stop reading, which is worse than
    # not having it.
    today = _dt.date.today().isoformat()
    due = {e.get("slug") for e in rows if str(e.get("date", "9999")) <= today}

    for f in sorted(blog_dir.glob("*.html")):
        slug = f.stem
        if slug not in due:
            continue
        if slug not in listed:
            yield drift("post is listed",
                        f"blog/{slug}.html is due and deployed but nothing on "
                        f"/blog links to it — published, not listed",
                        ["blog.html is hand-maintained; add the card"])


def check_shipping_artefact_is_current():
    """The installer on disk is not older than the code it claims to contain.

    BECK CAUGHT THIS TWICE IN ONE DAY, 2026-08-28, and the second time it had
    already invalidated a whole verification run: the binary under test was
    built at 14:55 with eleven commits landed after it, so every result was
    about yesterday's product wearing today's commit hashes. She rebuilt and
    re-ran rather than report it.

    AND THE SIGNATURE IS THE QUIETER HALF. The `.sig` was NINE HOURS OLDER than
    the installer it signs. A stale signature does not fail loudly — it fails at
    the moment somebody downloads the thing and their machine refuses it, which
    is the worst possible place to find out.

    THE PRODUCT HAD NO VERSION IDENTIFIER, which is what made this necessary
    rather than merely tidy: every build reported 0.1.0, in the config, in
    Add/Remove Programs and in its own startup log, until Mason's fix on
    2026-08-29 bumped it to 0.2.0 (W4). That fix is not what this function
    checks, and does not retire it: a timestamp still tells a REBUILD apart
    from the one already tested, which a version number alone cannot do
    either -- two builds ten minutes apart can share the same 0.2.0.
    """
    installer = Path.home() / "Documents/JARVIS/desktop/installer/NameOS-Setup.exe"
    src = Path.home() / "Documents/JARVIS/desktop"
    if not installer.is_file():
        # No artefact is not drift — nothing has been built, which is honest.
        return
    built = installer.stat().st_mtime

    newer = []
    for sub in ("ui/index.html", "src-tauri/src", "installer/NameOS.nsi"):
        p2 = src / sub
        if not p2.exists():
            continue
        files = [p2] if p2.is_file() else list(p2.rglob("*.rs"))
        for f in files:
            if f.stat().st_mtime > built:
                newer.append(f.name)
    if newer:
        yield drift("shipping artefact",
                    f"NameOS-Setup.exe is older than {len(newer)} source file(s) it "
                    f"should contain — testing or shipping it tests the wrong build",
                    sorted(set(newer))[:6])

    sig = installer.with_suffix(".exe.sig")
    if sig.is_file() and sig.stat().st_mtime < built:
        gap = (built - sig.stat().st_mtime) / 3600
        yield drift("shipping artefact",
                    f"the .sig is {gap:.1f}h OLDER than the installer it signs — "
                    f"this must not be published",
                    [str(sig)])


def check_requests_are_moving():
    """An open request that nothing has touched all day gets named, not counted.

    MARK, 2026-08-29: "you keep saying that but also continue to let jobs fall",
    and then "i dont care how i care it gets addressed and doesn't keep
    happening."

    THE FAULT WAS NOT FORGETTING. On 2026-08-28 fifteen requests were logged and
    ZERO were closed, including seven that were finished and committed hours
    earlier. So fifteen entries all looked equally open, the list stopped being
    a signal, and five real items from that morning sat untouched for a whole
    day underneath the noise. Closing is part of finishing; a done item left
    open is not tidiness, it is camouflage over the work that actually needs
    doing.

    SO THIS NAMES THEM INDIVIDUALLY. A count is what let this happen -- "189
    open" tells nobody anything. An item whose timestamp is more than a day old
    and which is still open gets printed by name, every session start, until
    somebody either does it or closes it.
    """
    reqs = Path.home() / "Documents/JARVIS/REQUESTS.md"
    if not reqs.is_file():
        yield unchecked("requests moving", f"{reqs} is not readable")
        return
    try:
        text = reqs.read_text(encoding="utf-8")
    except Exception as exc:
        yield unchecked("requests moving", f"could not read it: {exc}")
        return

    today = _dt.date.today()
    stale = []
    for m in re.finditer(r"- \[ \] `(\d{4}-\d{2}-\d{2})[^`]*` \*\*(.{0,70})", text):
        try:
            age = (today - _dt.date.fromisoformat(m.group(1))).days
        except ValueError:
            continue
        if age >= 1:
            stale.append((age, " ".join(m.group(2).split())[:66]))

    if stale:
        # BOTH ENDS, NOT THE OLDEST. Vance ran this against the live file the
        # night it was written: 94 stale items, and showing the 8 oldest printed
        # nothing but 22-23 day fossils while the five REAL items from the
        # previous morning -- the ones this check exists to surface -- sorted to
        # the bottom and could never appear. The fix built in response to Mark's
        # correction reproduced the exact fault it was built to prevent: an
        # instrument confidently pointed at the wrong end of the question.
        #
        # The recent end is where live work is. The old end is where things go
        # to be closed. Both are worth naming and neither can be reached from
        # one sort order.
        stale.sort(reverse=True)
        oldest, newest = stale[:4], stale[-4:]
        lines = [f"{a}d — {ti}" for a, ti in newest]
        lines.append("--- and the oldest, which are probably dead or done ---")
        lines += [f"{a}d — {ti}" for a, ti in oldest]
        yield drift("requests moving",
                    f"{len(stale)} open request(s) untouched for a day or more",
                    lines)


def check_facts_fit_a_dispatch():
    """Will FACTS.md actually arrive whole, or is its tail being cut off?

    WHY THIS EXISTS. `hooks/facts-gate.py` attaches FACTS.md to every dispatch
    and TRUNCATES it past MAX_CHARS. On 2026-08-29 the file crossed that cap
    three times in one day, and the third time it did so on the very commit
    recording the most important finding of the day — so the newest and most
    load-bearing lines were exactly the part being silently cut.

    That is the file's own failure mode: it exists so nobody briefs from
    memory, and a source that arrives half-missing still reads as
    authoritative. Nothing announced it. Both times it was caught only because
    I happened to look at a byte count.

    So the size is checked rather than remembered, and it warns BEFORE the
    cliff — a file at 98% of the cap is one paragraph from silently losing its
    tail, and by then the person adding that paragraph has moved on.
    """
    facts = JARVIS / "FACTS.md"
    gate = JARVIS / "hooks" / "facts-gate.py"
    if not facts.exists():
        yield drift("facts file", "FACTS.md is missing",
                    ["it is attached to every dispatch; without it every "
                     "number in every brief is recollection"])
        return
    try:
        cap = int(re.search(r"^MAX_CHARS\s*=\s*(\d+)", gate.read_text(encoding="utf-8"),
                            re.M).group(1))
    except Exception as exc:
        yield unchecked("facts file",
                        f"could not read MAX_CHARS from facts-gate.py: "
                        f"{type(exc).__name__}")
        return
    size = len(facts.read_text(encoding="utf-8"))
    if size > cap:
        yield drift("facts file",
                    f"FACTS.md is {size} chars against a {cap} cap — "
                    f"{size - cap} chars are being CUT from every dispatch",
                    ["the tail is the newest material, so the most recent "
                     "finding is the part specialists never see"])
    elif size > cap * 0.95:
        yield drift("facts file",
                    f"FACTS.md is {size} of {cap} chars — one paragraph from "
                    "truncating every dispatch",
                    ["prune it now; it is a short list of load-bearing "
                     "numbers, not a history"])


CHECKS = (
    ("facts fit a dispatch", check_facts_fit_a_dispatch),
    ("agent count", check_agent_count),
    ("post is listed", check_post_is_listed),
    ("requests moving", check_requests_are_moving),
    ("shipping artefact", check_shipping_artefact_is_current),
    ("cloud approval rows", check_cloud_approval_rows),
    ("site assets", check_site_assets_exist),
    ("stylesheet cache", check_stylesheet_cache_busting),
    ("site links", check_site_links_resolve),
    ("offline gate", check_offline_gate),
    ("web access count", check_web_access_count),
    ("omission count", check_roster_omission_count),
    ("roster names", check_roster_names_have_agents),
    ("ledger recording", check_ledger_is_recording),
    ("brain ledger code", check_brain_has_the_ledger_code),
    ("open dispatches", check_open_dispatches),
    ("roster stamp", check_roster_stamp),
    ("log permissions", check_roster_perms),
    ("uncommitted work", check_uncommitted),
    ("process vs source", check_process_versus_source),
    ("loopback split", check_loopback_claim),
    ("public hostname", check_public_hostname),
    ("no raw-rest deploy", check_no_raw_rest_deploy_import),
    ("board caching", check_board_refuses_caching),
    ("stale threshold", check_threshold_matches_board),
    ("unit list", check_unit_list_matches_board),
    ("fronted http", check_bare_fronted_http),
)


def collect() -> tuple[list[Finding], list[str]]:
    """Run every check. Returns (findings, names of checks that ran clean).

    THE try/except IS THE WHOLE CONTRACT. A check that raises becomes a visible
    "could not check" line naming the exception type, and the run continues. It
    must never be possible for a bug in one check to take out the others, and it
    must never be possible for a bug anywhere in here to take out the session
    that ran it.

    A check that yields nothing is a check that VERIFIED something, and its name
    goes in the clean list so -v can show what silence actually covered.
    """
    findings: list[Finding] = []
    clean: list[str] = []
    for name, check in CHECKS:
        try:
            produced = list(check())
        except Exception as exc:                      # noqa: BLE001 - see above
            findings.append(unchecked(
                name, f"the check itself raised {type(exc).__name__}: "
                      f"{str(exc)[:120]}"))
            continue
        if produced:
            findings.extend(produced)
        else:
            clean.append(name)
    return findings, clean


def report(findings: list[Finding], clean: list[str], verbose: bool) -> int:
    """Print what disagrees, and nothing else. Returns the exit code."""
    drifts = [f for f in findings if f.kind == DRIFT]
    blocked = [f for f in findings if f.kind == UNCHECKED]

    if drifts:
        print(f"DRIFT — {len(drifts)} thing(s) no longer match what this box "
              f"says about itself\n")
        for finding in drifts:
            print(f"  [{finding.check}] {finding.message}")
            for line in finding.detail:
                print(f"      {line}")
            print()

    if blocked:
        # Never folded in with the drift list. "I looked and it was wrong" and
        # "I could not look" are different answers, and collapsing them is how
        # a skipped check becomes a silent pass.
        print(f"COULD NOT CHECK — {len(blocked)}; these are NOT passes\n")
        for finding in blocked:
            print(f"  [{finding.check}] {finding.message}")
            for line in finding.detail:
                print(f"      {line}")
            print()

    if verbose and clean:
        print(f"VERIFIED — {len(clean)} check(s) found nothing:")
        for name in clean:
            print(f"  {name}")
        print()

    if drifts:
        return 1
    if blocked:
        return 2
    return 0


def main(argv: list[str]) -> int:
    verbose = "-v" in argv or "--verbose" in argv
    findings, clean = collect()
    return report(findings, clean, verbose)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:                          # noqa: BLE001
        # The last line of the never-raise rule. If something got past every
        # wrapper, say so on stderr and exit as "could not check" — never a
        # traceback into whatever ran this, and never a 0.
        print(f"drift-check itself failed: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        sys.exit(2)
