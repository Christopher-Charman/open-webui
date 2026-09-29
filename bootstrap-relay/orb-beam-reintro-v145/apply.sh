#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="$PKG/frontend"
FSTATIC="$FRONTEND/static"
SSTATIC="$PKG/static"
INDEX="$FRONTEND/index.html"
RESTART="$BASE/restart-openwebui-via-passenger.sh"

PIN="2fa5b68f901547b85c8083e73d28ad6404df0069"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/orb-beam-reintro-v145/install.py"

TMP="$(mktemp)"
OUT="$(mktemp)"
PUB="$(mktemp)"
ORBJS="$(mktemp)"
ORBCSS="$(mktemp)"
HDRJS="$(mktemp)"
HDRCSS="$(mktemp)"
trap 'rm -f "$TMP" "$OUT" "$PUB" "$ORBJS" "$ORBCSS" "$HDRJS" "$HDRCSS"' EXIT

rollback_layer() {
  local backup="$1"
  [ -n "$backup" ] || return 0
  echo "=== AUTO ROLLBACK ORB/BEAM LAYER ==="

  if [ -f "$backup/frontend/index.html" ]; then
    cp -p "$backup/frontend/index.html" "$INDEX"
  fi

  for name in owui-orb-v1.js owui-orb-v1.css continuity-orb-beam-postmount.js; do
    if [ -f "$backup/frontend/static/$name" ]; then
      cp -p "$backup/frontend/static/$name" "$FSTATIC/$name"
    else
      rm -f "$FSTATIC/$name"
    fi
    if [ -f "$backup/served/static/$name" ]; then
      cp -p "$backup/served/static/$name" "$SSTATIC/$name"
    else
      rm -f "$SSTATIC/$name"
    fi
  done

  "$RESTART" >/dev/null 2>&1 || true
  echo "ORB_BEAM_REINTRO=ROLLBACK_AUTO_RESTORED"
}

curl -fsSL --retry 3 --connect-timeout 10 "$RAW" -o "$TMP"
python3 "$TMP" | tee "$OUT"

grep -Fq 'ORB_BEAM_REINTRO=STAGED_ON_DISK_PASS' "$OUT" || {
  echo "ORB_BEAM_REINTRO=FAIL staging_receipt_missing"
  exit 2
}

BACKUP="$(awk -F= '/^BACKUP=/{print $2}' "$OUT" | tail -1)"
CSS_SHA_EXPECTED="$(awk -F= '/^ORB_CSS_DERIVED_SHA256=/{print $2}' "$OUT" | tail -1)"
JS_SHA_EXPECTED="$(awk -F= '/^ORB_JS_SHA256=/{print $2}' "$OUT" | tail -1)"

[ -n "$BACKUP" ] || {
  echo "ORB_BEAM_REINTRO=FAIL backup_receipt_missing"
  exit 2
}
[ "$JS_SHA_EXPECTED" = "71fab45c74489a147a3184044574da6d29051684f7848b59c3bb5627d58badc7" ] || {
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL unexpected_staged_js_sha256=$JS_SHA_EXPECTED"
  exit 2
}
[ -n "$CSS_SHA_EXPECTED" ] || {
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL derived_css_sha_missing"
  exit 2
}

test -x "$RESTART" || {
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL restart_script_missing"
  exit 2
}

if ! "$RESTART"; then
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL restart_failed"
  exit 2
fi

local_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18080/health || true)"
if [ "$local_code" != "200" ]; then
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL local_health_http=$local_code"
  exit 2
fi

stamp="$(date +%s)"
if ! curl -fsSL --retry 3 --connect-timeout 10 --max-time 25 \
  -H 'Cache-Control: no-cache' -H 'Pragma: no-cache' \
  "https://powerpc-darwin.org/?__orb_beam_v145=$stamp" -o "$PUB"
then
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL public_html_fetch"
  exit 2
fi

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$PUB" || {
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL accepted_ui_voice_marker_missing"
  exit 2
}
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$PUB" || {
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL orb_beam_marker_missing"
  exit 2
}

loader_bytes="$(curl -fsSL --max-time 15 "https://powerpc-darwin.org/static/loader.js?cb=$stamp" | wc -c | tr -d ' ')"
custom_css_bytes="$(curl -fsSL --max-time 15 "https://powerpc-darwin.org/static/custom.css?cb=$stamp" | wc -c | tr -d ' ')"

if [ "$loader_bytes" != "0" ] || [ "$custom_css_bytes" != "0" ]; then
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL stock_bootstrap_changed loader=$loader_bytes css=$custom_css_bytes"
  exit 2
fi

js_code="$(curl -sS -D "$HDRJS" -o "$ORBJS" -w '%{http_code}' --max-time 20 \
  "https://powerpc-darwin.org/static/owui-orb-v1.js?cb=$stamp" || true)"
css_code="$(curl -sS -D "$HDRCSS" -o "$ORBCSS" -w '%{http_code}' --max-time 20 \
  "https://powerpc-darwin.org/static/owui-orb-v1.css?cb=$stamp" || true)"

js_type="$(awk 'BEGIN{IGNORECASE=1} /^content-type:/{gsub(/\r/,""); print $2}' "$HDRJS" | tail -1)"
css_type="$(awk 'BEGIN{IGNORECASE=1} /^content-type:/{gsub(/\r/,""); print $2}' "$HDRCSS" | tail -1)"

if [ "$js_code" != "200" ] || [[ "$js_type" != *javascript* ]]; then
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL orb_js_delivery http=$js_code content_type=$js_type"
  exit 2
fi
if [ "$css_code" != "200" ] || [[ "$css_type" != *css* ]]; then
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL orb_css_delivery http=$css_code content_type=$css_type"
  exit 2
fi

js_sha="$(sha256sum "$ORBJS" | awk '{print $1}')"
css_sha="$(sha256sum "$ORBCSS" | awk '{print $1}')"

if [ "$js_sha" != "$JS_SHA_EXPECTED" ]; then
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL public_js_sha256=$js_sha expected=$JS_SHA_EXPECTED"
  exit 2
fi
if [ "$css_sha" != "$CSS_SHA_EXPECTED" ]; then
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL public_css_sha256=$css_sha expected=$CSS_SHA_EXPECTED"
  exit 2
fi

grep -Fq 'ORB_VERSION = 1.4.5' "$ORBJS" || {
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL orb_version_marker_missing"
  exit 2
}
grep -Fq 'owui-border-beam-v1' "$ORBJS" || {
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL border_beam_marker_missing"
  exit 2
}
grep -Fq 'continuity-landing-hero-150-v20260930.1' "$ORBCSS" || {
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL landing_hero_150_marker_missing"
  exit 2
}
for token in '615px' '162px' '123px' '489px' '141px' '111px'; do
  grep -Fq "$token" "$ORBCSS" || {
    rollback_layer "$BACKUP"
    echo "ORB_BEAM_REINTRO=FAIL landing_hero_geometry_missing=$token"
    exit 2
  }
done

VOICE="$(curl -fsSL --max-time 20 "https://powerpc-darwin.org/static/pwa-voice-bridge.js?cb=$stamp")"
printf '%s' "$VOICE" | grep -Fq "1.3.4-nowarm" || {
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL accepted_voice_bridge_missing"
  exit 2
}
if printf '%s' "$VOICE" | grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe'; then
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL accepted_voice_boundary_regressed"
  exit 2
fi

tts_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18082/health || true)"
pocket_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18083/health || true)"
if [ "$tts_code" != "200" ] || [ "$pocket_code" != "200" ]; then
  rollback_layer "$BACKUP"
  echo "ORB_BEAM_REINTRO=FAIL voice_backend_health tts=$tts_code pocket=$pocket_code"
  exit 2
fi

echo "ORB_BEAM_REINTRO=PUBLIC_PASS"
echo "layer=POSTMOUNT_ORB_BORDERBEAM_V145_PLUS_LANDING_HERO_150"
echo "orb_source_version=1.4.5"
echo "landing_hero_scale=1.5"
echo "landing_desktop_target=615x162_orb123"
echo "landing_mobile_target=489x141_orb111_viewport_capped"
echo "active_chat_geometry=UNCHANGED_V1.4.5"
echo "ui_voice_layer=PRESERVED"
echo "voice_bridge=1.3.4-nowarm"
echo "client_model_runtime=ABSENT"
echo "voice_warm_calls=ABSENT"
echo "stock_loader_bytes=$loader_bytes"
echo "stock_custom_css_bytes=$custom_css_bytes"
echo "orb_js_sha256=$js_sha"
echo "orb_css_derived_sha256=$css_sha"
echo "rollback=$BACKUP"
echo "NEXT=DEVICE_TEST_LANDING_AND_ACTIVE_CHAT_IN_SAFARI_THEN_HOME_SCREEN"
