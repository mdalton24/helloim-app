# Moving Jarvis onto Sam

**The machine itself is built separately — see [[SAM-SETUP]].**
This document is only the move.

Written 2026-08-10, after Mark reinstalled Sam and asked for the steps.

**Read the four decisions at the bottom first.** Three of them are his alone, and
two of them change what the rest of this plan even looks like.

---

## What is actually being moved

Right now this VM runs everything and has no GPU. Sam has the 5090 and has been a
worker. Moving means Sam becomes the machine, and the VM becomes either a backup
or nothing.

Seven services live here today:

| service | what it is | GPU helps? |
|---|---|---|
| `voiceline-whisper` | speech to text | **yes, a lot** |
| `voiceline-kokoro` | text to speech | **yes** |
| `voiceline-voiceprint` | speaker verification | yes |
| `voiceline-client` | the turn loop and input endpoint | no |
| `voiceline-brain` | the Claude session that thinks | no |
| `voiceline-board` | the visualizer on :8777 | no |
| `markdalton-site` | the public site origin on :8779 | no |
| `cloudflared` | the tunnel that publishes both | no |

**The three GPU services are the whole argument for moving.** Today they run on a
machine with no graphics card at all.

---

## THE ONE THAT WILL BITE: encrypted credentials do not travel

**`systemd-creds` encryption is bound to the machine.** Every `.cred` file on this
box is undecryptable on Sam. They cannot be copied — they have to be recreated
from the original secret, and **we no longer hold the plaintext for any of them**,
because destroying the plaintext is the rule.

So each one needs re-obtaining, and only Mark can do most of it:

| credential | how it comes back |
|---|---|
| Cloudflare API token | reissue in the dashboard |
| Discord bot token | Reset Token in the portal (free) |
| Discord admin token | same |
| voice-line / board tokens | regenerate locally, no outside party |
| Google Workspace service account | **a JSON key file, so this one CAN be copied** — it is at `~/.config/jarvis-workspace/service-account.json`, `0600` |
| Alpaca | gone, deliberately, 2026-08-09 |

**Do this properly on arrival, not later:** re-encrypt on Sam with
`systemd-creds encrypt --user`, `chmod 600`, then `shred -u` the plaintext.

---

## The order, and why it is this order

### 1–6. Preparing the machine — SEE [[SAM-SETUP]]

**Those steps are not here any more.** Building Sam from a blank Ubuntu — SSH,
sudo, the toolchain, Node, ollama and the models — is a different job from moving
Jarvis onto it, and mixing the two is how a document stops being followable.

**`SAM-SETUP.md` records what was actually run and what came back**, on
2026-08-10. As of writing, steps 1 through 5 there are done and the models are
downloading.

**Do not start anything below until that document's checklist passes.** Migrating
onto a machine that cannot compile, cannot deploy and has no models is migrating
onto a slower version of nothing.

### 7. Move the data
`~/Documents` (the vault, every specialist folder, the record), `~/voice-line`,
`~/voice-visualizer`, `~/markdalton-site`, `~/.claude`, `~/local-llm`, the systemd
user units, `~/.config`.
**`rsync -a` to preserve permissions**, then **verify `0600`/`0700` afterwards
rather than trusting it** — a file here once declared itself `0600` in its own
text and was `0664` on disk.

### 8. Claude Code itself
**This is the part that is actually "me".** Install it, sign in, and confirm it
reads `CLAUDE.md` and the vault at boot. **Until this works, nothing above
matters** — the services would run with nobody home.

### 9. systemd
Copy the units, `systemctl --user daemon-reload`, then
**`loginctl enable-linger mdalton`** or nothing survives a logout. Start them in
dependency order and read each log rather than trusting `active`.

### 10. The tunnel — LAST, and only once
**It can only run in one place at a time.** Pointing Sam's tunnel at the same
hostname while this box still serves it is how both break. Stop it here, start it
there, verify from outside, and keep the rollback one command away.

---

## Four decisions, and three are only Mark's

1. **Does the private record move to a laptop?** `~/Documents/KIDS` is `0700`,
   outside git, deliberately not in the vault. A laptop is portable, and portable
   means losable. **This is his call and I will not assume it.**
2. **Is Sam always on?** The board, the tunnel and the 5am check assume a machine
   that is up. A closed laptop is fine — the lid rule keeps the GPU warm — but a
   laptop that leaves the house is a different thing.
3. **Does this VM stay?** Keeping it as a cold standby costs nothing and means a
   bad migration is survivable. Deleting it means the tunnel and the record exist
   in exactly one place.
4. **All at once, or the GPU services first?** *(mine to recommend.)* **Move
   whisper, kokoro and voiceprint first and leave everything else here.** They are
   the entire reason to move, they gain the most, and they do not touch the tunnel
   or the record. If that works for a week, move the rest. A single big cutover
   at 2am is how a system disappears.

---

## What I can do without asking

Everything from step 2 to step 7, on Sam, once I can reach it — Mark's standing
instruction of 2026-08-08: *"you are responsible for it… updates, performance,
jobs, optimization, etc. You dont have to ask me."*

**What I will not do without a word:** move the record, touch the tunnel, or stop
anything on this box.
