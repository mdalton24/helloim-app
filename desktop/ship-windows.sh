#!/usr/bin/env bash
# Build helloim.ai for Windows and put the INSTALLER on Mark's desktop.
#
# IT SHIPS THE INSTALLER AND NOTHING ELSE, and that is the whole point of this
# file existing rather than a one-liner in /tmp.
#
# THE SCAR, 2026-08-26. Every build until now also copied the bare NameOS.exe
# next to the installer. That file is a fully standalone binary: it needs no
# install, writes no registry key, and the uninstaller cannot touch it because
# it was never installed. So Mark uninstalled NameOS, correctly, and NameOS kept
# opening -- and the obvious conclusion was that the uninstaller was broken. It
# was not. It removed the program files and both registry keys perfectly. What
# it could not remove was a loose copy I had left on his desktop.
#
# "Here is a portable one as well" reads as generous and is actually a second,
# invisible installation that nothing manages: it never updates, it is not in
# Add/Remove Programs, and it survives every uninstall. One artefact, one way in,
# one way out.
#
#   ./ship-windows.sh              build, package, copy to the desktop
#   ./ship-windows.sh --no-ship    build and package only
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET=x86_64-pc-windows-msvc
HOST=mdalt@10.0.0.51
DEST='C:/Users/mdalt/OneDrive/Desktop'

source "$HOME/.cargo/env" 2>/dev/null || true
export PATH="/usr/local/bin:$PATH"

# THE WINDOWS SDK IS CASE-INSENSITIVE AND THIS DISK IS NOT. Adding the ONNX
# runtime made the linker ask for "DirectML.lib" and "PathCch.lib"; cargo-xwin
# unpacks them as "directml.lib" and "pathcch.lib", and the build died on two
# libraries that were sitting right there. Self-healing rather than a note in a
# file, because the cache is rebuilt whenever xwin updates.
XWIN_LIB="$HOME/.cache/cargo-xwin/xwin/sdk/lib/um/x86_64"
for want in DirectML:directml PathCch:pathcch; do
  have="${want#*:}"; want="${want%%:*}"
  [ -e "$XWIN_LIB/$want.lib" ] || [ ! -e "$XWIN_LIB/$have.lib" ] \
    || ln -sf "$have.lib" "$XWIN_LIB/$want.lib"
done

echo "build start $(date +%H:%M:%S)"
cd "$HERE/src-tauri" || exit 1
"$HOME/.cargo/bin/cargo" xwin build --release --target "$TARGET" 2>&1 | tail -4

EXE="$HERE/src-tauri/target/$TARGET/release/remembrancer.exe"
[ -f "$EXE" ] || { echo "WIN_FAIL: no binary at $EXE"; exit 1; }

# THE VOICE MODEL LINKS AGAINST DIRECTML, WHICH IS A SEPARATE DLL. An installer
# that carries only the exe hands over an app that will not start on any machine
# but this one -- and it would look like a broken download, not a missing file.
# So the DLL is found, checked, and staged with the binary. If it ever stops
# being emitted, this FAILS THE BUILD rather than quietly shipping without it.
DLL="$HERE/src-tauri/target/$TARGET/release/DirectML.dll"
[ -f "$DLL" ] || { echo "WIN_FAIL: no DirectML.dll beside the binary -- the installer would ship an app that cannot start"; exit 1; }

# THE EXE ALSO HAS ORDINARY (NON-DELAY) IMPORTS ON MSVCP140/140_1 AND
# VCRUNTIME140/140_1 -- Beck's NO-GO, 2026-09-05: a clean Windows 11 has none
# of them, so the process cannot even be created ("the code execution cannot
# proceed because MSVCP140.dll was not found"), no window, nothing for
# startup.rs's own fatal-dialog fallback to catch. `-C
# target-feature=+crt-static` was tried and rejected the same day -- it fails
# to LINK under cargo-xwin, because ort-sys's bundled ONNX Runtime objects
# expect a dynamically-linked CRT.
#
# CHAINING vc_redist.x64.exe AT INSTALL TIME WAS TRIED SECOND, SHIPPED, AND
# FAILED ON BECK'S PRISTINE VM, SAME DAY: it is manifested
# `requireAdministrator`, this installer is deliberately per-user
# (`RequestExecutionLevel user`, Mark's own decision), and the elevation
# prompt it raised had nobody on the secure desktop to answer it -- 776
# seconds stuck, install dead mid-Section, 182 MB stranded with no
# uninstaller. Full story in NameOS.nsi beside the DLL `File` block.
#
# SO: NO INSTALLER RUNS, EVER. `vc_redist.x64.exe` is fetched here only as a
# SOURCE to unpack -- extract-vcrt.py pulls the eight x64 CRT DLLs out of it
# (it is a WiX Burn bundle; see that script's own header for the container
# layout) into installer/vcrt/, and NameOS.nsi stages them beside the exe
# app-local, no elevation, no ExecWait. Redistributing them this way is a use
# Microsoft's own docs describe directly:
#   https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files
#
# Fetched once and reused on every build after that, same idiom as the voice
# pack below: THE BUILD FAILS if the download is missing/truncated, or if
# extraction cannot find all eight DLLs, because a release-blocking DLL fault
# is exactly the kind of thing that must never ship quietly a second time.
# aka.ms/vs/17/release/vc_redist.x64.exe is Microsoft's own permanent
# redirect to the current x64 v14 redistributable
# (https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) --
# verified live 2026-09-05: 301 to download.visualstudio.microsoft.com, then
# 200, ~24.4 MB.
VCREDIST="$HERE/installer/vc_redist.x64.exe"
if [ ! -s "$VCREDIST" ]; then
  echo "fetching vc_redist.x64.exe (once)…"
  curl -fsSL --retry 3 -o "$VCREDIST.part" "https://aka.ms/vs/17/release/vc_redist.x64.exe" \
    && mv "$VCREDIST.part" "$VCREDIST" || rm -f "$VCREDIST.part"
fi
sz=$(stat -c%s "$VCREDIST" 2>/dev/null || echo 0)
[ "$sz" -ge 20000000 ] || { echo "WIN_FAIL: vc_redist.x64.exe is $sz bytes -- nothing to extract the VC++ runtime from"; exit 1; }

VCRT_DIR="$HERE/installer/vcrt"
VCRT_FILES="concrt140.dll msvcp140.dll msvcp140_1.dll msvcp140_2.dll msvcp140_atomic_wait.dll msvcp140_codecvt_ids.dll vcruntime140.dll vcruntime140_1.dll"
need_extract=0
for f in $VCRT_FILES; do
  [ -s "$VCRT_DIR/$f" ] || need_extract=1
done
if [ "$need_extract" = 1 ]; then
  echo "extracting the VC++ runtime DLLs from vc_redist.x64.exe (once)…"
  python3 "$HERE/extract-vcrt.py" "$VCREDIST" "$VCRT_DIR" || { echo "WIN_FAIL: extract-vcrt.py could not pull the runtime DLLs out of vc_redist.x64.exe"; exit 1; }
fi
for f in $VCRT_FILES; do
  [ -s "$VCRT_DIR/$f" ] || { echo "WIN_FAIL: installer/vcrt/$f is missing -- the installer would ship an app that cannot start"; exit 1; }
done

# THE NATURAL VOICES SHIP IN THE BOX -- Mark, 2026-08-26: "can we package this
# into our installer so they dont have to go and download."
#
# Fetched once into the installer directory and reused on every build after
# that; they are 115 MB and they do not change. THE BUILD FAILS if they are
# missing rather than quietly producing a small installer that still sends
# people off to download -- a silently smaller artefact is exactly the kind of
# regression nobody notices until a user does.
VOICE_DIR="$HERE/installer/tts"
mkdir -p "$VOICE_DIR"
KOKORO_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx"
VOICES_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
for want in "kokoro.onnx:$KOKORO_URL:60000000" "voices.bin:$VOICES_URL:20000000"; do
  name="${want%%:*}"; rest="${want#*:}"; url="${rest%:*}"; min="${rest##*:}"
  f="$VOICE_DIR/$name"
  if [ ! -s "$f" ]; then
    echo "fetching $name (once)…"
    curl -fsSL --retry 3 -o "$f.part" "$url" && mv "$f.part" "$f" || rm -f "$f.part"
  fi
  # A truncated download is worse than none: it installs, and then the voices
  # fail at the moment somebody presses play.
  sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
  [ "$sz" -ge "$min" ] || { echo "WIN_FAIL: $name is $sz bytes -- the installer would ship a broken voice pack"; exit 1; }
done

# NOTHING IS BUNDLED TO MAKE CONNECTORS WORK -- Mark, 2026-08-26: "We should
# only be using things native to windows before resorting to other items to
# force things to happen."
#
# He is right and this is the correction. An hour earlier this script was
# fetching a 70 MB Node runtime so the connector tiles could run somebody
# else's JavaScript, which is the definition of forcing it. The tiles now point
# at HOSTED servers -- Notion, GitHub, Figma, Airtable and the rest all publish
# one, every endpoint was probed and answers -- so there is no runtime to
# install, nothing to keep up to date, and no second language in the box.
# Email is served by our own compiled binary rather than by npx.
#
# The voices stay bundled, and that is not the same thing: they are DATA the
# app itself reads, not a runtime for running other people's code.

# ONE VERSION NUMBER, READ FROM tauri.conf.json. It is the one the running app
# reports about itself, so it is the one the update server compares against --
# and the installer has to register the same string in Add/Remove Programs or
# the two disagree about what is installed. When they disagreed, every machine
# was offered the same update forever.
VERSION=$(python3 -c "import json,sys;print(json.load(open('$HERE/src-tauri/tauri.conf.json'))['version'])") \
  || { echo "WIN_FAIL: could not read the version out of tauri.conf.json"; exit 1; }
echo "version $VERSION"

cd "$HERE/installer" || exit 1
cp "$EXE" ./helloim.ai.exe        # staged FOR the installer to embed, not for shipping
cp -L "$DLL" ./DirectML.dll       # -L: it is a symlink into the ort cache
makensis -DVERSION="$VERSION" NameOS.nsi 2>&1 | tail -1   # script file itself is unrenamed, see NameOS.nsi header
[ -f helloim.ai-Setup.exe ] || { echo "WIN_FAIL: makensis produced no installer"; exit 1; }

# A NEW INSTALLER INVALIDATES ANY OLD .sig SITTING BESIDE IT -- W3, Beck's
# release verification, 2026-08-29. This script never writes a .sig itself --
# publish-release.py's sign() does that, fresh, from whatever bytes are at
# helloim.ai-Setup.exe the moment it runs, and it always overwrites this file, so
# a normal publish is safe regardless. What is not safe is a person finding a
# .sig sitting here BETWEEN a build and a publish and trusting it: it signed
# the PREVIOUS installer, this script has no way to say so, and the two files
# do not even carry a version in their names to tell them apart by eye (see
# W4 -- that used to be permanently true, now it is only true until the next
# rebuild). Removing it here means its only honest state between builds is
# "does not exist yet", never "exists and might be wrong".
rm -f helloim.ai-Setup.exe.sig

if [ "${1:-}" = "--no-ship" ]; then
  echo "packaged, not shipped: $HERE/installer/helloim.ai-Setup.exe"
  exit 0
fi

# SHIPPED IN TWO STEPS, AND THE SECOND ONE IS THE POINT -- Mark, 2026-08-26:
# "I dont have install file on my desktop." It WAS there, full size, at the
# exact path Windows uses for his desktop, written four minutes earlier.
# Explorer had simply never redrawn: a file arriving over SSH fires no shell
# change notification, so the icon does not appear until something refreshes.
#
# Copying to a .part name and letting WINDOWS do the final rename fixes it at
# the source -- the move is performed by Windows, so Windows tells its own
# shell, and the icon appears. It also means the desktop never shows a
# half-copied 99 MB installer that somebody might double-click.
if scp -o ConnectTimeout=15 -o BatchMode=yes helloim.ai-Setup.exe "$HOST:$DEST/helloim.ai-Setup.exe.part" >/dev/null 2>&1 \
   && ssh -o ConnectTimeout=15 -o BatchMode=yes "$HOST" "move /y \"${DEST//\//\\}\\helloim.ai-Setup.exe.part\" \"${DEST//\//\\}\\helloim.ai-Setup.exe\"" >/dev/null 2>&1; then
  echo "shipped helloim.ai-Setup.exe"
else
  echo "WIN_FAIL: could not reach $HOST"; exit 1
fi

# Say plainly if an old loose copy is still sitting there. It is HIS desktop and
# his file, so this reports and never deletes -- but leaving it unmentioned is
# how "I uninstalled it and it still runs" happens twice.
#
# STILL CHECKS FOR THE LITERAL OLD NAME "NameOS.exe", DELIBERATELY, as of the
# helloim.ai rename -- this is checking for a real leftover from BEFORE the
# rename, which really was written under that filename (see the scar above).
# It is not the new artifact's name, so it must not follow the rename.
if ssh -o ConnectTimeout=15 -o BatchMode=yes "$HOST" \
     'if exist "C:\Users\mdalt\OneDrive\Desktop\NameOS.exe" (exit 0) else (exit 1)' 2>/dev/null; then
  echo "NOTE: a loose NameOS.exe is still on the desktop. It runs without being"
  echo "      installed and no uninstall will remove it. Ask before deleting it."
fi
echo "DONE $(date +%H:%M:%S)"
