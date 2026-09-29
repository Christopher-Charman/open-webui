#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
RESTART="$BASE/restart-openwebui-via-passenger.sh"
LAUNCHER="$BASE/run-openwebui.sh"
PIN="16dc225e5f6f85d3291eaafd5f1ebb2045416317"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/restore-exact-1956/restore.py"
CACHE_GEN="restore-1956-20260929-r2"

TMP="$(mktemp)"
PUBLIC="$(mktemp)"
LOADER="$(mktemp)"
CSS="$(mktemp)"
VOICE="$(mktemp)"
trap 'rm -f "$TMP" "$PUBLIC" "$LOADER" "$CSS" "$VOICE"' EXIT

curl -fsSL --retry 3 --connect-timeout 10 "$RAW" -o "$TMP"
python3 "$TMP"

grep -Fq 'export WEBUI_AUTH=True' "$LAUNCHER" || {
  echo "RESTORE_1956=FAIL native_openwebui_auth_not_enabled"
  exit 2
}

test -x "$RESTART" || {
  echo "RESTORE_1956=FAIL restart_script_missing"
  exit 2
}

"$RESTART"

local_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18080/health || true)"
[ "$local_code" = "200" ] || {
  echo "RESTORE_1956=FAIL local_health_http=$local_code"
  exit 2
}

probe="https://powerpc-darwin.org/?__restore1956=$(date +%s)"
curl -fsSL --retry 3 --connect-timeout 10 --max-time 25 \
  -H 'Cache-Control: no-cache' -H 'Pragma: no-cache' \
  "$probe" -o "$PUBLIC" || {
    echo "RESTORE_1956=FAIL public_html_fetch"
    exit 2
  }

grep -Fq "owui-exact-1956-restore:$CACHE_GEN" "$PUBLIC" || {
  echo "RESTORE_1956=FAIL public_restore_marker_missing"
  exit 2
}
grep -Fq "/static/loader.js?v=$CACHE_GEN" "$PUBLIC" || {
  echo "RESTORE_1956=FAIL public_loader_generation_missing"
  exit 2
}
grep -Fq "/static/custom.css?v=$CACHE_GEN" "$PUBLIC" || {
  echo "RESTORE_1956=FAIL public_css_generation_missing"
  exit 2
}

for bad in owui-pwa-legacy-chats-bypass-v20260929.5 owui-pwa-startup-guard-v20260929.6 .pwa20260929_6.js; do
  if grep -Fq "$bad" "$PUBLIC"; then
    echo "RESTORE_1956=FAIL post_checkpoint_residue=$bad"
    exit 2
  fi
done

curl -fsSL --retry 3 --max-time 20 "https://powerpc-darwin.org/static/loader.js?v=$CACHE_GEN&cb=$(date +%s)" -o "$LOADER"
curl -fsSL --retry 3 --max-time 20 "https://powerpc-darwin.org/static/custom.css?v=$CACHE_GEN&cb=$(date +%s)" -o "$CSS"
curl -fsSL --retry 3 --max-time 20 "https://powerpc-darwin.org/static/pwa-voice-bridge.js?v=$CACHE_GEN&cb=$(date +%s)" -o "$VOICE"

loader_sha="$(sha256sum "$LOADER" | awk '{print $1}')"
css_sha="$(sha256sum "$CSS" | awk '{print $1}')"
voice_sha="$(sha256sum "$VOICE" | awk '{print $1}')"

[ "$loader_sha" = "e101590a26011b7d804470936333075dc97c20131e7d70bffd889754b35e2f39" ] || {
  echo "RESTORE_1956=FAIL public_loader_sha256=$loader_sha"; exit 2;
}
[ "$css_sha" = "475abc34859bc632461e6bd66bef2e2893fdc8e108035ce5a0617461a6469484" ] || {
  echo "RESTORE_1956=FAIL public_css_sha256=$css_sha"; exit 2;
}
[ "$voice_sha" = "ad38be628a364e50f4f495970b0c2381bc10ac2f64e3acf8bf8f0313fa14b0f6" ] || {
  echo "RESTORE_1956=FAIL public_voice_sha256=$voice_sha"; exit 2;
}

grep -Fq 'window.__CONTINUITY_BOOTSTRAP_ISOLATED__ = true' "$LOADER" || {
  echo "RESTORE_1956=FAIL bootstrap_isolation_marker_missing"; exit 2;
}

# Validate the established voice services without warming/synthesizing anything.
tts_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18082/health || true)"
pocket_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18083/health || true)"

echo "RESTORE_1956=PUBLIC_PASS"
echo "native_openwebui_auth=PASS"
echo "local_openwebui_health_http=$local_code"
echo "tts_health_http=$tts_code"
echo "pocket_health_http=$pocket_code"
echo "cache_generation=$CACHE_GEN"
echo "loader_sha256=$loader_sha"
echo "custom_css_sha256=$css_sha"
echo "voice_bridge_sha256=$voice_sha"
echo "NEXT=DEVICE_FORCE_CLOSE_REOPEN_EXISTING_HOME_SCREEN_PWA_AND_SAFARI"
