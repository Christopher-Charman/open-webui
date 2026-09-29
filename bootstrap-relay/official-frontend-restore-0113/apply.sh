#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="$PKG/frontend"
SERVED_STATIC="$PKG/static"
RESTART="$BASE/restart-openwebui-via-passenger.sh"

WHEEL_URL="https://files.pythonhosted.org/packages/4c/e4/28abecd6b75fa6fa40ae181d2fa9f57593e26d13309c90531dee5b4acc28/open_webui-0.11.3-py3-none-any.whl"
WHEEL_SHA256="8436f9bb29c5accbdfd90d78470fcc917c882bd53f72ed88fed91b1ee97fa547"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="$BASE/runtime-domains/pwa-repair-agent/official-frontend-restore-$STAMP"
BACKUP="$BASE/runtime-domains/pwa-repair-agent/backups/pre-official-frontend-$STAMP"
WHEEL="$WORK/open_webui-0.11.3-py3-none-any.whl"
EXTRACT="$WORK/extract"
STAGED="$WORK/frontend"

mkdir -p "$WORK" "$EXTRACT" "$BACKUP"

echo "=== DOWNLOAD OFFICIAL OPENWEBUI 0.11.3 WHEEL ==="
curl -fL --retry 3 --connect-timeout 15 "$WHEEL_URL" -o "$WHEEL"

echo "$WHEEL_SHA256  $WHEEL" | sha256sum -c -

echo "=== EXTRACT OFFICIAL FRONTEND ONLY ==="
python3 - "$WHEEL" "$EXTRACT" <<'PY'
import sys, zipfile
wheel, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(wheel) as z:
    names = [n for n in z.namelist() if n.startswith("open_webui/frontend/")]
    if not names:
        raise SystemExit("ERROR official wheel contains no open_webui/frontend tree")
    for n in names:
        z.extract(n, out)
print("WHEEL_FRONTEND_ENTRIES=%d" % len(names))
PY

cp -a "$EXTRACT/open_webui/frontend" "$STAGED"

echo "=== VERIFY CLEAN FRONTEND COHERENCE ==="
python3 - "$STAGED" <<'PY'
from pathlib import Path
import re, sys, hashlib
root = Path(sys.argv[1])
index = root / "index.html"
if not index.is_file():
    raise SystemExit("ERROR clean index.html missing")

text = index.read_text()

# Official 0.11.3 extension points must be inert.
for rel in ("static/loader.js", "static/custom.css"):
    p = root / rel
    if not p.is_file():
        raise SystemExit("ERROR clean %s missing" % rel)
    if p.stat().st_size != 0:
        raise SystemExit("ERROR clean %s expected empty, got %d bytes" % (rel, p.stat().st_size))

# Every immutable URL directly referenced by the stock document must exist.
refs = sorted(set(re.findall(r'/_app/immutable/[^"\'<>\s)]+', text)))
missing = []
for ref in refs:
    local = root / ref.lstrip("/")
    if not local.is_file():
        missing.append(ref)

if missing:
    print("MISSING_IMMUTABLE_REFERENCES=%d" % len(missing))
    for ref in missing:
        print("MISSING=" + ref)
    raise SystemExit("ERROR official frontend document is internally incoherent")

# The preload and bootstrap import must agree on the app entry.
preloads = re.findall(r'/_app/immutable/entry/(app\.[A-Za-z0-9_-]+\.js)', text)
imports = re.findall(r'import\(["\']/(_app/immutable/entry/app\.[A-Za-z0-9_-]+\.js)["\']\)', text)
preload_names = sorted(set(preloads))
import_names = sorted(set(Path(x).name for x in imports))
if len(preload_names) != 1 or len(import_names) != 1 or preload_names != import_names:
    raise SystemExit("ERROR official app-entry preload/import mismatch: %r vs %r" % (preload_names, import_names))

print("OFFICIAL_FRONTEND_COHERENCE=PASS")
print("OFFICIAL_APP_ENTRY=" + preload_names[0])
print("IMMUTABLE_DIRECT_REFS=%d" % len(refs))
print("OFFICIAL_INDEX_SHA256=" + hashlib.sha256(index.read_bytes()).hexdigest())
PY

echo "=== BACKUP CURRENT MUTATED FRONTEND ==="
cp -a "$FRONTEND" "$BACKUP/frontend"
if [ -d "$SERVED_STATIC" ]; then
  cp -a "$SERVED_STATIC" "$BACKUP/served-static"
fi

echo "=== ATOMIC FRONTEND REPLACEMENT ==="
OLD="$PKG/frontend.pre-official-swap-$STAMP"
mv "$FRONTEND" "$OLD"
if ! mv "$STAGED" "$FRONTEND"; then
  mv "$OLD" "$FRONTEND"
  echo "OFFICIAL_FRONTEND_RESTORE=ROLLBACK_AUTO_RESTORED"
  exit 2
fi

# Retain the pre-swap tree inside the timestamped rollback set.
mv "$OLD" "$BACKUP/frontend-live-pre-swap"

echo "=== RESTART OPENWEBUI ==="
"$RESTART"

local_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18080/health || true)"
[ "$local_code" = "200" ] || {
  echo "OFFICIAL_FRONTEND_RESTORE=FAIL local_health_http=$local_code"
  exit 2
}

echo "=== VERIFY PUBLIC DOCUMENT + ASSETS ==="
PUB_HTML="$WORK/public.html"
curl -fsSL --retry 3 --connect-timeout 10 --max-time 30 \
  -H 'Cache-Control: no-cache' -H 'Pragma: no-cache' \
  "https://powerpc-darwin.org/?__official_frontend=$STAMP" -o "$PUB_HTML"

python3 - "$FRONTEND" "$PUB_HTML" <<'PY'
from pathlib import Path
import re, sys
root = Path(sys.argv[1])
html = Path(sys.argv[2]).read_text()

# No custom boot-layer references may remain in the official document.
bad = (
    "pwa-client-runtime.js",
    "pwa-voice-bridge.js",
    "lcars-runtime.js",
    "continuity-shell-registry.js",
    "continuity-controls.js",
    "continuity-settings.js",
    "owui-orb",
    "stock-bootstrap-20260929",
    "chatstartupfix20260929",
)
for token in bad:
    if token in html:
        raise SystemExit("ERROR public document still contains custom/stale token: " + token)

preloads = re.findall(r'/_app/immutable/entry/(app\.[A-Za-z0-9_-]+\.js)', html)
imports = re.findall(r'import\(["\']/(_app/immutable/entry/app\.[A-Za-z0-9_-]+\.js)["\']\)', html)
p = sorted(set(preloads))
i = sorted(set(Path(x).name for x in imports))
if len(p) != 1 or len(i) != 1 or p != i:
    raise SystemExit("ERROR public preload/import mismatch: %r vs %r" % (p, i))

print("PUBLIC_APP_ENTRY_COHERENCE=PASS")
print("PUBLIC_APP_ENTRY=" + p[0])
PY

# Verify all directly referenced immutable assets return the expected MIME family,
# not the HTML SPA fallback.
python3 - "$PUB_HTML" "$WORK/asset-list.txt" <<'PY'
from pathlib import Path
import re, sys
html = Path(sys.argv[1]).read_text()
refs = sorted(set(re.findall(r'/_app/immutable/[^"\'<>\s)]+', html)))
Path(sys.argv[2]).write_text("\n".join(refs) + "\n")
print("PUBLIC_DIRECT_IMMUTABLE_REFS=%d" % len(refs))
PY

fail=0
while IFS= read -r ref; do
  [ -n "$ref" ] || continue
  headers="$WORK/hdr.$(printf '%s' "$ref" | sha256sum | cut -c1-16)"
  body="$WORK/body.$(printf '%s' "$ref" | sha256sum | cut -c1-16)"
  code="$(curl -sS -D "$headers" -o "$body" -w '%{http_code}' --max-time 20 "https://powerpc-darwin.org$ref?cb=$STAMP" || true)"
  ctype="$(awk 'BEGIN{IGNORECASE=1} /^content-type:/{gsub(/\r/,""); print $2}' "$headers" | tail -1)"
  case "$ref" in
    *.js)
      if [ "$code" != "200" ] || [[ "$ctype" != *javascript* ]]; then
        echo "ASSET_FAIL=$ref http=$code content_type=$ctype"
        fail=1
      fi
      ;;
    *.css)
      if [ "$code" != "200" ] || [[ "$ctype" != *css* ]]; then
        echo "ASSET_FAIL=$ref http=$code content_type=$ctype"
        fail=1
      fi
      ;;
  esac
done < "$WORK/asset-list.txt"

[ "$fail" = "0" ] || {
  echo "OFFICIAL_FRONTEND_RESTORE=FAIL public_asset_mime_or_http"
  exit 2
}

echo "OFFICIAL_FRONTEND_RESTORE=PUBLIC_PASS"
echo "frontend_source=PYPI_OPEN_WEBUI_0.11.3_OFFICIAL_WHEEL"
echo "wheel_sha256=$WHEEL_SHA256"
echo "backend_data_changed=NO"
echo "native_auth_changed=NO"
echo "local_health_http=$local_code"
echo "rollback=$BACKUP"
echo "NEXT=FORCE_CLOSE_REOPEN_SAFARI_THEN_HOME_SCREEN_PWA"
