#!/usr/bin/env python3
"""Push a NameOS update out to everybody running it.

Mark, 2026-08-27: "also design a way to push updates."

WHAT PUSHING AN UPDATE ACTUALLY IS HERE, in three steps, and the order is the
whole safety argument:

  1. **Sign the installer.** A minisign signature over the exact bytes, made
     with a key that lives encrypted on this box and nowhere else. The app
     carries the matching public key inside its own binary and refuses to run
     anything that does not verify against it.
  2. **Upload the installer** to R2, where the app can fetch it.
  3. **Publish the manifest** to KV -- and only now does any machine learn the
     new version exists.

STEP 3 IS LAST FOR A REASON. The manifest is the only thing anybody reads, so
until it is written the release is invisible. Upload a broken file and nobody
has been offered it. Do it the other way round and there is a window where
every NameOS on earth is trying to download a file that is not there yet.

  publish-release.py                     sign, upload, publish to stable
  publish-release.py --rollout 10        offer it to a tenth of installs
  publish-release.py --channel beta      publish where only opted-in boxes look
  publish-release.py --notes "..."       what changed, shown in the app
  publish-release.py --dry-run           sign and check; upload and publish nothing
  publish-release.py --withdraw          THE KILL SWITCH -- see below

--withdraw is the thing worth knowing about before you need it. It rewrites the
manifest back to the previous release, and because every app asks the server
rather than being pushed to, the offer stops within the minute. It does not
reach back into machines that already installed; nothing can. That is what
--rollout is for -- so a bad release was only ever offered to a tenth of them.

SECRETS. The signing key and its password are decrypted at call time via
systemd-creds and piped straight into the signer. Neither is ever written to a
file or placed in argv.
"""
import argparse
import base64
import datetime
import hashlib
import hmac
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

ACC = "78e66b8988065564b5bdcd3c7af57f28"
KV_TITLE = "nameos-releases"
BUCKET = "nameos-downloads"
# Served by the Worker off its R2 binding rather than from a public bucket or an
# r2.dev address. One hostname for the whole product, one TLS certificate, and
# the download cannot outlive the site it belongs to.
PUBLIC_BASE = "https://nameos.ai/download/"
# The one platform NameOS ships on today. Tauri builds the key as
# "{target}-{arch}"; the Worker looks the installed machine up by the same
# string. Adding macOS later means another entry here, not a new mechanism.
PLATFORM = "windows-x86_64"
# THIS SCRIPT MUST IDENTIFY ITSELF, AND THAT IS NOT COSMETIC -- see
# verify_published(). Cloudflare refuses `Python-urllib/...` on this zone.
VERIFY_UA = "NameOS-release/1.0 (publish-release.py)"

HERE = pathlib.Path(__file__).resolve().parent
CONF = HERE / "src-tauri" / "tauri.conf.json"
# The local build artifact ship-windows.sh writes. Renamed from
# NameOS-Setup.exe to match productName "helloim.ai" in the 2026-09-02
# rename -- the DOWNLOAD name uploaded to R2 stays NameOS-Setup-<ver>.exe
# (see `name` in main() and the Worker allow-list), only this local file
# moved. Pointing at the old name signed a stale pre-rename installer.
SETUP = HERE / "installer" / "helloim.ai-Setup.exe"
CRED_DIR = pathlib.Path.home() / ".config" / "nameos"
CF_CRED_DIR = pathlib.Path.home() / ".config" / "cloudflare"
TAURI = pathlib.Path.home() / ".cargo" / "bin" / "cargo"


def cred(name, path):
    out = subprocess.run(
        ["systemd-creds", "decrypt", "--user", f"--name={name}", str(path), "-"],
        capture_output=True)
    v = out.stdout.decode().strip()
    if not v:
        die(f"could not decrypt {name} from {path}: {out.stderr.decode().strip()}")
    return v


def die(msg):
    sys.exit(f"RELEASE_FAIL: {msg}")


def api(token, path, method="GET", data=None, headers=None, raw=None):
    url = "https://api.cloudflare.com/client/v4" + path
    h = {"Authorization": f"Bearer {token}"}
    if headers:
        h.update(headers)
    body = raw
    if body is None and data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"success": False, "errors": [{"message": e.reason}]}


def ok(status, body):
    return status < 400 and isinstance(body, dict) and body.get("success")


# --------------------------------------------------------------------------
# 1. SIGN
# --------------------------------------------------------------------------

def sign(installer):
    """Minisign the installer with the key that only exists here, encrypted.

    THE KEY IS THE PRODUCT'S ONLY DEFENCE against somebody serving a different
    installer from a compromised bucket. Losing it means no machine already in
    the world can ever be updated again -- they would all reject the new
    signature. Backing it up is a real task and not a nicety.
    """
    key = CRED_DIR / "updater-key.cred"
    pw = CRED_DIR / "updater-pw.cred"
    if not key.exists():
        die(f"no signing key at {key} -- nothing can be published without it")

    # THROUGH THE ENVIRONMENT OF THIS ONE CHILD, and not by any of the three
    # routes that look easier. `-p <password>` puts it in argv, where `ps` can
    # read it. `-f <path>` needs the decrypted key written to disk first, even
    # briefly. Exporting these in a shell leaves them set for everything that
    # runs afterwards. Handed to one subprocess, they exist for the length of
    # one command and are never in this process's own environment.
    env = dict(os.environ)
    env["TAURI_SIGNING_PRIVATE_KEY"] = cred("nameos-updater-key", key)
    env["TAURI_SIGNING_PRIVATE_KEY_PASSWORD"] = cred("nameos-updater-pw", pw)
    out = subprocess.run(
        [str(TAURI), "tauri", "signer", "sign", str(installer)],
        capture_output=True, cwd=str(HERE), env=env)

    sigfile = installer.with_suffix(installer.suffix + ".sig")
    if out.returncode != 0 or not sigfile.exists():
        die("signing failed: " + (out.stderr.decode() or out.stdout.decode())[:400])
    sig = sigfile.read_text().strip()
    if not sig:
        die("the signer produced an empty signature")
    return sig


# --------------------------------------------------------------------------
# 2. UPLOAD
#
# Over the S3-compatible endpoint, not the Cloudflare REST API. That is not a
# preference: R2's object read/write permission is only honoured by the S3
# endpoint, so the REST route returns 401 no matter how the token is scoped.
# --------------------------------------------------------------------------

def _sigv4(method, host, path, payload_sha, key_id, secret, region="auto",
           service="s3", when=None):
    when = when or datetime.datetime.now(datetime.timezone.utc)
    amz = when.strftime("%Y%m%dT%H%M%SZ")
    day = when.strftime("%Y%m%d")
    headers = {
        "host": host,
        "x-amz-content-sha256": payload_sha,
        "x-amz-date": amz,
    }
    signed = ";".join(sorted(headers))
    canon_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    canon = "\n".join([method, path, "", canon_headers, signed, payload_sha])
    scope = f"{day}/{region}/{service}/aws4_request"
    to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amz, scope,
        hashlib.sha256(canon.encode()).hexdigest(),
    ])

    def h(k, m):
        return hmac.new(k, m.encode(), hashlib.sha256).digest()

    k = h(h(h(h(("AWS4" + secret).encode(), day), region), service), "aws4_request")
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={key_id}/{scope}, "
        f"SignedHeaders={signed}, Signature={sig}")
    return headers


R2_KEY = CF_CRED_DIR / "r2-key-id.cred"
R2_SECRET = CF_CRED_DIR / "r2-secret.cred"


def r2_ready():
    """Are the R2 credentials even on this box?

    CHECKED BEFORE SIGNING, NOT DURING UPLOAD. Signing a hundred-megabyte
    installer takes real time, and discovering afterwards that the credential
    for the next step does not exist is a minute spent to learn something a
    stat() answers instantly. Verified missing on 2026-08-29: neither file
    exists and cf-adpanda-worker is not scoped for R2 either, so this is the
    live state of the box and not a hypothetical.
    """
    return R2_KEY.exists() and R2_SECRET.exists()


def verify_published(url, data):
    """Can anybody actually DOWNLOAD what we just uploaded?

    THIS IS THE CHECK THAT WOULD HAVE CAUGHT TONIGHT'S GAP. The manifest is the
    only thing any machine reads, and it carries a URL. On 2026-08-29 that URL
    -- https://nameos.ai/download/... -- answered 404 for every possible name,
    because the Worker had no /download route and no R2 binding at all. Publish
    into that and every NameOS on earth is offered a version it cannot fetch,
    and the only symptom is a failed download on somebody else's machine.

    So: fetch the real URL over the real internet, and compare the bytes to
    what was uploaded. A hash rather than a length -- a length matches for a
    cached older build of the same size, which is exactly the confusion that
    already cost this product a release.

    THE USER-AGENT ON THIS REQUEST IS LOAD-BEARING. Cloudflare answers 403 to
    `Python-urllib/...` across the WHOLE nameos.ai zone -- every path, not just
    this one -- and urllib sends that by default. So this check failed 403 on an
    installer that was sitting in R2 perfectly, and it failed AFTER the upload,
    which is the expensive half. Measured 2026-08-31: urllib default -> 403,
    while `reqwest/...` and `tauri-updater/...` -> 404. **THE REAL APP IS NOT
    AFFECTED** -- tauri-plugin-updater fetches with reqwest, which the zone
    accepts. This was only ever the publisher's own client being refused.
    """
    req = urllib.request.Request(url, headers={"User-Agent": VERIFY_UA})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            got = r.read()
    except urllib.error.HTTPError as e:
        die(f"the installer is not downloadable at {url} (HTTP {e.code}). "
            "NOTHING WAS PUBLISHED. A 403 here is almost certainly the zone's "
            f"WAF refusing this script's User-Agent ({VERIFY_UA!r}), NOT a "
            "broken release -- rule that out BEFORE touching the Worker's "
            "/download route or its DOWNLOADS r2_bucket binding, both of which "
            "were verified good on 2026-08-31. See nameos/RELEASING.md.")
    except Exception as e:
        die(f"could not fetch {url}: {e}. NOTHING WAS PUBLISHED.")
    if hashlib.sha256(got).hexdigest() != hashlib.sha256(data).hexdigest():
        die(f"{url} served {len(got)} bytes that are not the installer we just "
            f"uploaded ({len(data)} bytes). NOTHING WAS PUBLISHED.")
    print(f"verified downloadable: {url} ({len(got) / 1e6:.1f} MB, hash matches)")


def upload(installer, key_name):
    kid = cred("r2-key-id", R2_KEY)
    secret = cred("r2-secret", R2_SECRET)
    data = installer.read_bytes()
    host = f"{ACC}.r2.cloudflarestorage.com"
    path = f"/{BUCKET}/{key_name}"
    # SHA-256 of the whole body. R2 checks it, so a truncated upload is refused
    # at the far end rather than becoming an installer that fails halfway
    # through on somebody's machine.
    headers = _sigv4("PUT", host, path, hashlib.sha256(data).hexdigest(), kid, secret)
    headers["Content-Type"] = "application/vnd.microsoft.portable-executable"
    req = urllib.request.Request(f"https://{host}{path}", data=data,
                                 headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            if r.status not in (200, 201):
                die(f"R2 upload returned {r.status}")
    except urllib.error.HTTPError as e:
        die(f"R2 upload failed: {e.code} {e.read()[:300].decode(errors='replace')}")
    return PUBLIC_BASE + key_name


# --------------------------------------------------------------------------
# 3. PUBLISH
# --------------------------------------------------------------------------

def kv_id(token):
    s, b = api(token, f"/accounts/{ACC}/storage/kv/namespaces?per_page=100")
    if not ok(s, b):
        die(f"could not list KV namespaces: {s} {b}")
    for n in b["result"]:
        if n["title"] == KV_TITLE:
            return n["id"]
    die(f"KV namespace {KV_TITLE} does not exist -- run nameos/deploy.py first")


def kv_get(token, ns, key):
    url = f"/accounts/{ACC}/storage/kv/namespaces/{ns}/values/{key}"
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4" + url,
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read())
    except Exception:
        return None


def kv_put(token, ns, key, value):
    s, b = api(token, f"/accounts/{ACC}/storage/kv/namespaces/{ns}/values/{key}",
               "PUT", headers={"Content-Type": "text/plain"},
               raw=json.dumps(value).encode())
    if not ok(s, b):
        die(f"could not write {key}: {s} {json.dumps(b)[:300]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="stable")
    ap.add_argument("--rollout", type=int, default=100,
                    help="percent of installs offered this version (1-100)")
    ap.add_argument("--notes", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollout-only", action="store_true",
                    help="change the percentage on what is already published, "
                         "without rebuilding, re-signing or re-uploading")
    ap.add_argument("--withdraw", action="store_true",
                    help="pull the current release and put the previous one back")
    a = ap.parse_args()

    if not (1 <= a.rollout <= 100):
        die("--rollout is a percentage from 1 to 100")

    cf = cred("cf-adpanda-worker", CF_CRED_DIR / "adpanda-worker.cred")
    ns = kv_id(cf)
    key = f"release:{a.channel}"

    if a.withdraw:
        cur = kv_get(cf, ns, key)
        prev = (cur or {}).get("previous")
        # --dry-run USED TO BE IGNORED ON THIS PATH AND ON --rollout-only,
        # which meant `--dry-run --withdraw` really withdrew the release. Found
        # 2026-08-29. A flag whose whole purpose is "touch nothing" must mean
        # that on every path that takes it, or it is worse than not existing --
        # somebody reaches for it precisely when they are unsure.
        if a.dry_run:
            print(f"dry run: would roll {a.channel} back to "
                  f"{prev['version'] if prev else '(nothing -- it would refuse)'}")
            return
        if not prev:
            # Writing an empty manifest would be the other kind of correct: every
            # machine stops being offered anything, including the good version
            # they are already happy on. That is fine, and it should be a
            # decision somebody makes out loud rather than a fallback.
            die("nothing to roll back to. To stop all updates on this channel, "
                f"delete the KV key {key} by hand.")
        prev.pop("previous", None)
        kv_put(cf, ns, key, prev)
        print(f"withdrawn. {a.channel} is back to {prev['version']}")
        return

    # WIDENING A ROLLOUT IS NOT A NEW RELEASE. Re-running the full publish to
    # go from 10% to 100% would sign and upload the same 100 MB again, and --
    # worse -- record the release it is replacing as its own `previous`, so
    # --withdraw would roll back to itself and appear to do nothing.
    if a.rollout_only:
        cur = kv_get(cf, ns, key)
        if not cur or not cur.get("version"):
            die(f"nothing is published on {a.channel} yet")
        was = cur.get("rollout", 100)
        if a.dry_run:
            print(f"dry run: would move {a.channel} {cur['version']} "
                  f"from {was}% to {a.rollout}%")
            return
        cur["rollout"] = a.rollout
        kv_put(cf, ns, key, cur)
        print(f"{a.channel} {cur['version']}: {was}% -> {a.rollout}%")
        return

    version = json.loads(CONF.read_text())["version"]
    if not SETUP.exists():
        die(f"no installer at {SETUP} -- run ./ship-windows.sh --no-ship first")

    # THE INSTALLER MUST BE NEWER THAN THE BUILD IT CAME FROM. A stale
    # NameOS-Setup.exe left over from the previous version signs and uploads
    # perfectly and ships the old app under the new version number -- the one
    # failure here that produces no error anywhere and cannot be undone by
    # publishing again, because every machine now believes it is up to date.
    #
    # THIS GUARD ONLY WATCHED tauri.conf.json AND THAT WAS NOT ENOUGH -- Beck,
    # 2026-08-28, first-release go/no-go, caught live rather than in principle:
    # installer 01:44, ui/index.html 01:59, guard returns False, and it would
    # have signed and shipped a build 15.5 minutes older than the UI.
    # The reason is structural, not an oversight: THE UI HAS NO BUILD STEP. It
    # is one hand-written file, so editing it never moves tauri.conf.json and
    # never moved anything else this guard looked at. Every UI-only change in
    # this product's history was invisible here -- including tonight's.
    # It now compares against the newest of everything the installer is built
    # FROM: the config, the frontend (frontendDist is ../ui) and the Rust
    # sources. Naming the offending file is deliberate -- "something is stale"
    # sends you hunting; "ui/index.html is newer" tells you what to rebuild for.
    newest, newest_src = CONF.stat().st_mtime, CONF
    for root in (HERE / "ui", HERE / "src-tauri" / "src"):
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            if f.is_file():
                m = f.stat().st_mtime
                if m > newest:
                    newest, newest_src = m, f
    if SETUP.stat().st_mtime < newest:
        die(f"the installer is older than {newest_src.relative_to(HERE)} -- it "
            "was built before the current source. Rebuild it before publishing.")

    # THE NAME THE WORKER WILL ACCEPT, checked here rather than discovered as a
    # 404 on somebody's machine. nameos/worker.js serves /download/<name> off an
    # ALLOW-LIST: NameOS-Setup-<major>.<minor>.<patch>[-prerelease].exe. A
    # version that does not fit uploads perfectly and is then unreachable.
    name = f"NameOS-Setup-{version}.exe"
    if not re.fullmatch(r"NameOS-Setup-\d{1,4}\.\d{1,4}\.\d{1,4}(?:-[0-9A-Za-z.]{1,32})?\.exe", name):
        die(f"version {version!r} produces the file name {name!r}, which the "
            "Worker's /download allow-list will refuse. Keep DOWNLOAD_NAME in "
            "nameos/worker.js and this pattern in step.")

    # BEFORE SIGNING, because signing a hundred megabytes is not free and
    # neither is the surprise.
    if not a.dry_run and not r2_ready():
        die("the R2 credentials are not on this box "
            f"({R2_KEY.name} / {R2_SECRET.name} under {CF_CRED_DIR}), so the "
            "installer cannot be uploaded and NOTHING has been published. "
            "See nameos/RELEASING.md for how they are minted and stored.")

    size = SETUP.stat().st_size
    print(f"version {version}  installer {size / 1e6:.1f} MB")
    sig = sign(SETUP)
    print(f"signed ({len(sig)} chars)")

    if a.dry_run:
        print(f"dry run: would upload {name} and publish {key} at {a.rollout}%")
        print(f"dry run: R2 credentials {'present' if r2_ready() else 'MISSING'}")
        return

    url = upload(SETUP, name)
    print(f"uploaded {url}")

    # AND ONLY NOW IS IT ALLOWED TO BECOME VISIBLE. Between the upload and the
    # manifest there is one more question worth asking, because it is the one
    # that was wrong tonight: can anybody actually fetch it?
    verify_published(url, SETUP.read_bytes())

    manifest = {
        "version": version,
        "notes": a.notes,
        "pub_date": datetime.datetime.now(datetime.timezone.utc)
                    .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "rollout": a.rollout,
        "platforms": {PLATFORM: {"url": url, "signature": sig}},
    }
    # Kept so --withdraw has somewhere to go back to. Exactly ONE deep: the
    # nested copy is stripped, or every manifest carries the entire history of
    # the product and grows past KV's value limit eventually.
    prev = kv_get(cf, ns, key)
    if prev:
        prev.pop("previous", None)
        manifest["previous"] = prev

    kv_put(cf, ns, key, manifest)
    print(f"published {version} to {a.channel} at {a.rollout}%")
    if a.rollout < 100:
        print(f"widen it later with:  {sys.argv[0]} --rollout-only --rollout 100")
    print(f"pull it back with:    {sys.argv[0]} --withdraw"
          + (f" --channel {a.channel}" if a.channel != "stable" else ""))


if __name__ == "__main__":
    main()
