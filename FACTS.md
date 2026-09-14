# Facts

**A fact goes in a brief only if it's in here or you checked it this session.**
Recollection is not a source. Wrong line? Fix it. **KEEP IT SHORT — the tail is
silently cut on the way into a dispatch.** A stale entry is worse than a missing
one; it rides along wearing this file's authority. Versions rot fastest.

---

## Money and offers
- **ADPanda: $500 build, +$50 install, +custom monthly for ads.** Off adpanda.com. **NOT $2,500.**
- **markdalton.com consulting is a SEPARATE business** — never carry a price, pitch, or segment between them.
- **Two outreach emails ever sent** (2026-08-22), no reply. n=2 can't fail (at 5.8% reply it returns zero 89% of the time). Smallest real test: 25 vs 25, one week.
- **Segment: foundation repair, nationwide, NO WEBSITE.** Boxing/salon closed. `foundation_type` still mandatory (the slab pitch ≠ what a basement contractor sells).
- **A WORKING WEBSITE HARD-BLOCKS SENDING** (Mark, 2026-08-31). Has a site → CRM record, never emailed. Nothing sends until a no-website list + rewritten copy exist.

## What is live
- adpanda.com — 200. Lead form → CF Worker + KV → timer → his inbox.
- markdalton.com — live; `/learn` Windows-only (2026-08-28).
- ~20 systemd timers overnight — each measures or delivers, none sells or contacts anyone.

## helloim.ai desktop app (= NameOS) — the Tauri app at `~/Documents/JARVIS/desktop`
- **Tauri, productName "helloim.ai", 0.2.0. WINDOWS ONLY — a Linux run is iteration, never evidence; Mark is the eyes.** Kokoro TTS, keyring = Windows Credential Manager, MCP connectors, native engine (`src-tauri/src/engine`), 10 faces in `ui/scenes/`.
- **APP IS ALREADY BRAIN-AGNOSTIC (Tessa 2026-09-05).** OpenAI/Gemini/OpenRouter/local connect + answer; Gemini tool-path fixed 2026-09-06 (thought_signature + parallel-call keying). `list_providers`=only claude on fresh install is CORRECT (roster, not catalogue). Do NOT "make it agnostic" or re-ask Mark about cloud. Cloud brains get the SAME tool surface as local (folder-scoped, opt-in for agency).
- **It's a visualizer + a voice — "we don't care what brain they connect it to."** A brain that can't edit files is NOT degraded; don't re-raise "but it loses tools."
- **`~/helloim-app` (Electron 0.2.8) is RETIRED — never build or verify on it** (caused 2 false NO-GOs).
- **Ship the 8 VC143 CRT DLLs app-local (beside the exe, like DirectML.dll); the installer is PER-USER (`RequestExecutionLevel user`) so a chained/elevated vc_redist hangs on a UAC prompt (Beck, 2026-09-05).** Mark's 10.0.0.51 already has the redist, so it proves nothing — fresh-VM launch is the only proof.
- **NSIS: two builds of identical source differ in hash** — a sha names an artifact, never grep the exe. **The broken installer once passed 10/10 clean runs — force the failure; verify his desktop, don't assume.**
- **ONBOARDING HOTKEY (2026-09-06, attempt 3).** App RegisterHotKeys 3 global chords at boot; Win32 then swallows WM_KEYDOWN for them. Fix1 (await suspend before Listening) fixed the ENTRY freeze but the freeze MOVED to EXIT: resume/re-register deadlocked the main thread (plugin's run_main_thread! blocks a command already ON the main thread). Fix2 (Mason): made the shortcut commands `async fn` + spawn_blocking. **Unprovable on Linux — Beck SendInput re-test is the gate: Responding stays True through commit/Esc/cancel AND ptt-hotkey.json written. Nothing ships to Mark until that passes.**
- **Local brain (in-app):** `llama3.2` ~4s; `gpt-oss:20b` never finishes a turn (and `detect_local_brain` defaults to it, unsorted); `WhiteRabbitNeo-13B` declares no tools. **Firefox headless hangs on WebGL — use Chromium.**

## ComfyUI — MARK'S PRIVATE WORK
- **Do NOT read `/history`, `/queue`, the `output` folder, or his saved workflows** (his instruction). Model files, folder listings, `/object_info` are fine.
- **NOW LOCAL on THIS box (sam), migrated from Windows 2026-09-06.** `~/ComfyUI` + venv `~/ComfyUI-venv` (py3.12, torch 2.11.0+cu128, sm_120), served loopback `127.0.0.1:8188` by `comfyui-local.service` (systemd user). Board `JARVIS_COMFY_VIA=local`; `studio.py` still the only socket (loopback only — unauth = RCE, never bind LAN). 13 models/62.6G at `~/ComfyUI/models` (byte-verified from Windows), custom node ComfyUI-GGUF. **`comfy-tunnel.service` to Windows is STOPPED + disabled** — do not restart it. Render proven on the 5090 2026-09-06.
- **Merging 2 images is possible, no download** — `TextEncodeQwenImageEditPlus` is a stock built-in taking 3 references; what a merge DOES (composite / style / subject move) is set by the PROMPT, not by separate graphs.
- **`shot_runner.convert_workflow_to_api` DOES NOT read `mode`** — it would run bypassed nodes live: two models at once on a 16 GB card.

## The brain
- **`brain_server.py` runs `claude` 2.1.226** (~25 behind). A restart needs announcing. Test the version we RUN, not the one we ship.

## OpenRouter — failover, proven 2026-09-01 by running it
- Key `openrouter-api`, `~/.config/openrouter/`. **$200 = ~a day at last week's ~$2,262 burn. FAILOVER, NOT migration.**
- **GPT-6 Astra: `openai/gpt-6-astra` on OpenRouter, $10/$50 per 1M, reasoning (proven 2026-09-05).** Answers on chat-completions AND `/v1/messages`; an Agents entry + a Mastermind seat. **OpenClaw is not a model** — a shell on local Ollama.

## Working with the box
- **This machine IS `sam` — 10.0.0.96, RTX 5090, 24 GB. Local first, always.**
- **Windows box `10.0.0.51` is his DAILY DRIVER — never reboot, never touch session 1.** Beck's rig + test account (`jarvis` / JARVIS2) live there. It has an **RTX 5080, 16 GB (NOT a second 5090), 64 GB RAM** (WMI reports a bogus ~4 GB — use `nvidia-smi`). **No interactive `jarvis` session** — `PrintWindow` returns TRUE and writes an all-black PNG; verify behaviorally.
- **GPU wedges on too many concurrent clients** — out of *contexts* (no VRAM guard sees it); `ps -eo stat | grep -c '^D'` is the number; render serially, one browser at a time.
- **Deploy markdalton.com with `edge/deploy-production.py --branch main --i-mean-it` and nothing else** — a bare `--branch <name>` is only a preview; it parity-refuses deleting live pages (name each with `--accept-deletion`).
- **Snap-confined browsers can't write to `/tmp`** — a screenshot reports success and leaves no file; write into `$HOME`.

## ESXi lab (mine) — 10.0.0.99
- **My box, ANY OS for testing.** root pw `~/.config/esxi/esxi-root.cred`; govc at `~/.local/bin`. Turnkey Win11 `esxi-deploy/deploy-win11.sh` (admin `jarvis/Testbox11!`, RDP on, phones home :8099, ~15 min). Current VM: Win11-Test 10.0.0.215.
- **Windows installer tests go HERE on a fresh VM, not 10.0.0.51.** Login: `xfreerdp3 /v:<ip> /u:jarvis /p:'Testbox11!' /cert:ignore` under Xvfb; never view the screenshot.
