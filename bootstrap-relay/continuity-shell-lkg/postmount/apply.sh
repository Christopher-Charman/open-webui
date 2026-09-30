#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE=""
for candidate in "${HOME}" "${HOME}/webapp" "${PWD}" "${PWD}/webapp"; do
  if [ -d "${candidate}/envs/openwebui/lib/python3.11/site-packages/open_webui" ]; then
    BASE="${candidate}"
    break
  fi
done
[ -n "$BASE" ] || {
  echo "ERROR unable to resolve webapp root"
  echo "HOME=${HOME}"
  echo "PWD=${PWD}"
  exit 2
}
BASE="$(cd "$BASE" && pwd -P)"
echo "BASE_RESOLVED=$BASE"

PKG="${BASE}/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="${PKG}/frontend"
INDEX="${FRONTEND}/index.html"
STATIC_A="${PKG}/static"
STATIC_B="${FRONTEND}/static"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="${BASE}/runtime-domains/pwa-repair-agent/backups/pre-semantic-binder-v2-${STAMP}"
GEN="20260930.2"
MARKER="continuity-shell-semantic-binder-v${GEN}"
REF="cf5fb5bf4c3f37e4332d914bc105c697ec019fa5"

[ -f "$INDEX" ] || { echo "ERROR index missing: $INDEX"; exit 2; }
mkdir -p "$STATIC_A" "$STATIC_B" "$BACKUP"

PROTECTED="$BACKUP/protected.before"
: > "$PROTECTED"
for p in   "$STATIC_A/loader.js"   "$STATIC_A/custom.css"   "$STATIC_A/pwa-voice-bridge.js"   "$STATIC_A/pwa-client-runtime.js"
do
  if [ -f "$p" ]; then
    printf '%s  %s\n' "$(sha256sum "$p" | awk '{print $1}')" "$p" >> "$PROTECTED"
  else
    printf 'ABSENT  %s\n' "$p" >> "$PROTECTED"
  fi
done

cp -a "$INDEX" "$BACKUP/index.html"
for name in continuity-shell-semantic-binder.js continuity-shell-semantic-binder.css; do
  [ -f "$STATIC_A/$name" ] && cp -a "$STATIC_A/$name" "$BACKUP/$name" || true
done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -fsSL   "https://raw.githubusercontent.com/Christopher-Charman/open-webui/${REF}/bootstrap-relay/continuity-shell-lkg/postmount/continuity-shell-semantic-binder.js"   -o "$TMP/continuity-shell-semantic-binder.js"
curl -fsSL   "https://raw.githubusercontent.com/Christopher-Charman/open-webui/${REF}/bootstrap-relay/continuity-shell-lkg/postmount/continuity-shell-semantic-binder.css"   -o "$TMP/continuity-shell-semantic-binder.css"

NODE="${BASE}/.local/node22-glibc217/bin/node"
if [ ! -x "$NODE" ]; then NODE="$(command -v node || true)"; fi
[ -n "$NODE" ] || { echo "ERROR node unavailable for syntax check"; exit 3; }
"$NODE" --check "$TMP/continuity-shell-semantic-binder.js"

grep -Fq "const VERSION='20260930.2'" "$TMP/continuity-shell-semantic-binder.js" || {
  echo "ERROR mapping-only binder version marker missing"
  exit 3
}
if grep -Eq 'continuity-hero-owned|continuity-footer-owned|continuity-chat-telemetry-owned|makeNeuralSvg|createElement\(.section.\)'   "$TMP/continuity-shell-semantic-binder.js" "$TMP/continuity-shell-semantic-binder.css"; then
  echo "ERROR binder still owns presentation nodes"
  exit 3
fi

install -m 0644 "$TMP/continuity-shell-semantic-binder.js" "$STATIC_A/continuity-shell-semantic-binder.js"
install -m 0644 "$TMP/continuity-shell-semantic-binder.css" "$STATIC_A/continuity-shell-semantic-binder.css"
install -m 0644 "$TMP/continuity-shell-semantic-binder.js" "$STATIC_B/continuity-shell-semantic-binder.js"
install -m 0644 "$TMP/continuity-shell-semantic-binder.css" "$STATIC_B/continuity-shell-semantic-binder.css"

python3 - "$INDEX" "$MARKER" "$GEN" <<'PY'
from pathlib import Path
import re, sys
p=Path(sys.argv[1]); marker=sys.argv[2]; gen=sys.argv[3]
s=p.read_text()

# Remove only prior semantic-binder injection blocks. No stock/bootstrap mutation.
pat=re.compile(
    r'\n?<!-- continuity-shell-semantic-binder-v[0-9.]+ -->.*?'
    r'<!-- /continuity-shell-semantic-binder-v[0-9.]+ -->\n?',
    re.S
)
s,n=pat.subn('\n',s)

block=f"""
<!-- {marker} -->
<link rel="stylesheet" href="/static/continuity-shell-semantic-binder.css?v={gen}">
<script defer src="/static/continuity-shell-semantic-binder.js?v={gen}"></script>
<!-- /{marker} -->
"""
needle="</body>"
if needle not in s:
    raise SystemExit("ERROR closing body not found")
p.write_text(s.replace(needle,block+"\n"+needle,1))
print(f"INDEX_BINDER_BLOCKS_REMOVED={n}")
print("INDEX_MARKER=INSTALLED_V2")
PY

while read -r before p; do
  if [ -f "$p" ]; then after="$(sha256sum "$p" | awk '{print $1}')"; else after="ABSENT"; fi
  if [ "$before" != "$after" ]; then
    echo "ERROR protected asset changed: $p"
    cp -a "$BACKUP/index.html" "$INDEX"
    exit 4
  fi
done < "$PROTECTED"

echo "SEMANTIC_BINDER_V2_STAGE=PASS"
echo "ownership=MAPPING_ONLY_NO_PRESENTATION_CREATION"
echo "BACKUP=$BACKUP"
echo "index_sha256=$(sha256sum "$INDEX" | awk '{print $1}')"
echo "binder_js_sha256=$(sha256sum "$STATIC_A/continuity-shell-semantic-binder.js" | awk '{print $1}')"
echo "binder_css_sha256=$(sha256sum "$STATIC_A/continuity-shell-semantic-binder.css" | awk '{print $1}')"
echo "stock_loader_bytes=$(wc -c < "$STATIC_A/loader.js" 2>/dev/null || printf ABSENT)"
echo "stock_custom_css_bytes=$(wc -c < "$STATIC_A/custom.css" 2>/dev/null || printf ABSENT)"
if [ -f "$STATIC_A/pwa-voice-bridge.js" ]; then
  echo "voice_bridge_sha256=$(sha256sum "$STATIC_A/pwa-voice-bridge.js" | awk '{print $1}')"
else
  echo "voice_bridge_sha256=ABSENT"
fi

PUBLIC="$TMP/public.html"
code="$(curl -sS -o "$PUBLIC" -w '%{http_code}' --max-time 12 "https://powerpc-darwin.org/?cb=$(date +%s)" || true)"
echo "public_http=$code"
if grep -Fq "$MARKER" "$PUBLIC" 2>/dev/null; then
  echo "PUBLIC_MARKER=PASS"
  echo "RESTART_REQUIRED=NO"
else
  echo "PUBLIC_MARKER=PENDING"
  echo "RESTART_REQUIRED=YES_BUT_NOT_PERFORMED_CONCURRENT_SESSION_BOUNDARY"
fi

echo "NEXT=DEVICE_TEST_LANDING_ONLY_THEN_ACTIVE_CHAT"
