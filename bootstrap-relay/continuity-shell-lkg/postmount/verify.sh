#!/usr/bin/env bash
set -Eeuo pipefail

BASE=""
for candidate in "${HOME}" "${HOME}/webapp" "${PWD}" "${PWD}/webapp"; do
  if [ -d "${candidate}/envs/openwebui/lib/python3.11/site-packages/open_webui" ]; then
    BASE="${candidate}"; break
  fi
done
[ -n "$BASE" ] || { echo "ERROR unable to resolve webapp root"; exit 2; }
BASE="$(cd "$BASE" && pwd -P)"

PKG="${BASE}/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="${PKG}/frontend"
STATIC="${PKG}/static"
INDEX="${FRONTEND}/index.html"
MARKER="continuity-shell-semantic-binder-v20260930.2"

echo "SEMANTIC_BINDER_V2_VERIFY=BEGIN"
echo "base=$BASE"
echo "index_marker=$(grep -Fc "$MARKER" "$INDEX" || true)"
echo "old_index_marker=$(grep -Fc 'continuity-shell-semantic-binder-v20260930.1' "$INDEX" || true)"
for f in continuity-shell-semantic-binder.js continuity-shell-semantic-binder.css; do
  if [ -f "$STATIC/$f" ]; then
    echo "$f=PASS bytes=$(wc -c < "$STATIC/$f") sha256=$(sha256sum "$STATIC/$f" | awk '{print $1}')"
  else
    echo "$f=MISSING"
  fi
done

if grep -Eq 'continuity-hero-owned|continuity-footer-owned|continuity-chat-telemetry-owned|makeNeuralSvg'   "$STATIC/continuity-shell-semantic-binder.js" "$STATIC/continuity-shell-semantic-binder.css"; then
  echo "ownership=FAIL_PRESENTATION_CREATION_PRESENT"
else
  echo "ownership=PASS_MAPPING_ONLY"
fi

echo "loader_bytes=$(wc -c < "$STATIC/loader.js" 2>/dev/null || printf ABSENT)"
echo "custom_css_bytes=$(wc -c < "$STATIC/custom.css" 2>/dev/null || printf ABSENT)"
if [ -f "$STATIC/pwa-voice-bridge.js" ]; then
  echo "voice_bridge_sha256=$(sha256sum "$STATIC/pwa-voice-bridge.js" | awk '{print $1}')"
fi

for u in   "https://powerpc-darwin.org/?cb=$(date +%s)"   "https://powerpc-darwin.org/static/continuity-shell-semantic-binder.js?cb=$(date +%s)"   "https://powerpc-darwin.org/static/continuity-shell-semantic-binder.css?cb=$(date +%s)"
do
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 12 "$u" || true)"
  echo "HTTP $code $u"
done

echo "SEMANTIC_BINDER_V2_VERIFY=END"
