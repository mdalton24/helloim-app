# Building Sam from a fresh Ubuntu install

**This is the machine, not the move.** Everything here turns a blank Ubuntu into
a box that can host Jarvis. Moving Jarvis onto it afterwards is a separate
document — [[MIGRATION-TO-SAM]].

Written as it was done, 2026-08-10, on Ubuntu 26.04 LTS. **Every command below
was actually run and every result is what came back**, not what should have.

Hardware: Alienware laptop, RTX 5090 Laptop GPU (24,463 MiB), 24 cores, 60 GB
RAM, 1.9 TB disk. Address `10.0.0.96`, hostname `Jarvis-Alienware-Laptop`.

---

## 0. What the fresh image already gave us

**Check before installing — two of these came free and one is the important one.**

| | state on a clean 26.04 |
|---|---|
| **NVIDIA driver** | **already installed** — 595.84, card visible to `nvidia-smi` |
| Python | 3.14.4 |
| rsync | 3.4.1 |
| everything else | missing: curl, git, gcc, cmake, ffmpeg, pip, node, npm, ollama |

**The driver being present matters more than anything else on this page.** It has
to exist before ollama or the speech build, or both compile happily against a
machine with no card and quietly fall back to CPU. **Prove it with
`nvidia-smi` before going further.** A CPU build looks identical until you time it.

---

## 1. SSH in

A fresh Ubuntu **desktop** install ships no SSH server, which is why port 22 is
closed and the machine still answers a ping. On Sam:

```
sudo apt update && sudo apt install openssh-server -y
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo '<the public key>' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
```

**On the machine connecting in, clear the old fingerprint first** or the first
connection is a scary warning rather than a login:

```
ssh-keygen -R 10.0.0.96
```

`~/.ssh/config` keeps `Host sam box96` pointing at `10.0.0.96` with
`IdentityFile ~/.ssh/id_ed25519_box96`. **`sam` is the name to use** — Mark's own
word, and mistaking it for a person has cost real work before.

---

## 2. Passwordless sudo

The old install had it; a fresh one does not, and **without it nothing below can
be installed by anyone but Mark.**

```
echo "mdalton ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/mdalton-nopasswd
sudo chmod 440 /etc/sudoers.d/mdalton-nopasswd
sudo visudo -c -f /etc/sudoers.d/mdalton-nopasswd
```

That last line is not optional — **a malformed sudoers file locks everyone out of
root**, and `visudo -c` is the check that stops it. It returned `parsed OK`.

**On the password.** Mark supplied his once so this could be set up. It was used
once, never stored, and scrubbed out of `.requests-inbox.md`, which captures
everything he types, within the same minute. **His password remains off limits as
a standing rule** — this was a one-time hand-over to bootstrap the thing that
replaces it, not a change to that rule.

---

## 3. Base toolchain

```
sudo apt-get update
sudo apt-get install -y curl git build-essential cmake ffmpeg python3-pip python3-venv rsync
```

Landed: curl 8.18.0, git 2.53.0, gcc 15.2.0, cmake 4.2.3, **ffmpeg 8.0.1**, pip 25.1.1.

**ffmpeg matters more than it looks.** It is how audio and video get made here —
the blog montage, the board captures, any future ticker — and it was missing on
the previous Sam until it was noticed and installed by hand.

---

## 4. Node — do not skip this one

```
sudo apt-get install -y nodejs npm
```

Landed: node v22.22.1, npm 9.2.0.

**This is the only reason the website can be deployed at all.** The JARVIS VM
cannot ship a Cloudflare Pages Function — the raw REST API cannot carry an
Advanced-Mode Worker, and Wrangler needs Node. That is precisely why the deploy
runs from Sam. **Lose Node and the site cannot be updated.**

Wrangler is not installed separately; it arrives through `npx`.

---

## 5. ollama and the models

```
curl -fsSL https://ollama.com/install.sh -o /tmp/ol.sh && sh /tmp/ol.sh
```

Installed 0.32.6, created and enabled the systemd service, and reported
**"NVIDIA GPU installed"** on its own. `curl http://127.0.0.1:11434/api/version`
answered, and `nvidia-smi` showed the card idle at 61 MiB of 24,463.

**It binds loopback only, deliberately.** Do not put it on the LAN to make
anything easier; the guarded tunnel in `ask-local.sh` is the way in.

Models pulled in the background — **roughly 100 GB and hours, not minutes:**

```
ollama pull gpt-oss:20b
ollama pull qwen2.5vl:7b
ollama pull hf.co/unsloth/Qwen3.6-35B-A3B-GGUF:UD-IQ4_XS
ollama pull qwen3-coder:30b
```

**Why these four.** `gpt-oss:20b` is the one measured correct on grounded
question-answering. **`qwen2.5vl` is the one that gives it eyes** — without a
vision model, anything visual has to go to the cloud, and that was true here
until 2026-08-09. The 35B is the general local model; the coder is for code.

---

## 6. Still to do on the machine itself

- **The lid rule.** A closed laptop must blank the screen and **not suspend**, or
  a shut lid means a cold GPU. It took both a logind drop-in **and** the GNOME
  setting last time — one alone was not enough.
- **Headroom guard.** `ask-local.sh` refuses at 75% VRAM / 85% GPU rather than
  queueing. A saturated box does not go slow, it goes unresponsive, and then
  somebody has to walk over and hold the power button.
- **Health check.** `check-box96.py` runs on a 30-minute timer and reports disk,
  temperature, VRAM, model count and whether work is queuing.
- **Decide about Cockpit.** The previous install ran a full web admin console on
  port 9090, bound to every interface, plus remote desktop on 3389/3390. **None
  of it was ours** — it came with the box. Worth deciding deliberately this time
  rather than discovering it again.

---

## The order, and why it is not arbitrary

1. **Driver first** or everything else builds for the wrong machine.
2. **SSH** or nobody can do the rest remotely.
3. **sudo** or nobody can install anything.
4. **Toolchain** before anything that compiles.
5. **Node** early, because losing it silently costs the ability to ship the site.
6. **Models last of the installs** — they are the only step measured in hours,
   so start them and do other things while they run.
