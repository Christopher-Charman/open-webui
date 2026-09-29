#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
RESTART="$BASE/restart-openwebui-via-passenger.sh"
PIN="3eeb2a6aab3931ef9f56d4fb5e9a66d70bec6998"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/orb-beam-reintro-v145/install.py"

TMP="$(mktemp)"
OUT="$(mktemp)"
PUB="$(mktemp)"
trap 'rm -f "$TMP" "$OUT" "$PUB"' EXIT

curl -fsSL --retry 3 --connect-timeout 10 "$RAW" -o "$TMP"
python3 "$TMP" | tee "$OUT"

grep -Fq 'ORB_BEAM_REINTRO=STAGED_ON_DISK_PASS' "$OUT" || {
  echo "ORB_BEAM_REINTRO=STOP staging_not_complete"
  exit 2
}

BACKUP="$(awk -F= '/^BACKUP=/{print $2}' "$OUT" | tail -1)"
[ -n "$BACKUP" ] || {
  echo "ORB_BEAM_REINTRO=STOP backup_receipt_missing"
  exit 2
}

"$RESTART"

[ "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18080/health || true)" = "200" ] || {
  echo "ORB_BEAM_REINTRO=FAIL openwebui_health"
  exit 2
}

stamp="$(date +%s)"
curl -fsSL --retry 3 --max-time 25 -H 'Cache-Control: no-cache' \
  "https://powerpc-darwin.org/?__orb_beam_v145=$stamp" -o "$PUB"

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$PUB" || {
  echo "ORB_BEAM_REINTRO=FAIL ui_voice_marker_missing"
  exit 2
}
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$PUB" || {
  echo "ORB_BEAM_REINTRO=FAIL orb_beam_marker_missing"
  exit 2
}

loader="$(curl -fsSL "https://powerpc-darwin.org/static/loader.js?cb=$stamp" | wc -c | tr -d ' ')"
custom="$(curl -fsSL "https://powerpc-darwin.org/static/custom.css?cb=$stamp" | wc -c | tr -d ' ')"
[ "$loader" = "0" ] && [ "$custom" = "0" ] || {
  echo "ORB_BEAM_REINTRO=FAIL stock_bootstrap_changed loader=$loader css=$custom"
  exit 2
}

ORBJS="$(curl -fsSL "https://powerpc-darwin.org/static/owui-orb-v1.js?cb=$stamp")"
ORBCSS="$(curl -fsSL "https://powerpc-darwin.org/static/owui-orb-v1.css?cb=$stamp")"
VOICE="$(curl -fsSL "https://powerpc-darwin.org/static/pwa-voice-bridge.js?cb=$stamp")"

printf '%s' "$ORBJS" | grep -Fq 'ORB_VERSION = 1.4.5' || {
  echo "ORB_BEAM_REINTRO=FAIL orb_version"
  exit 2
}
printf '%s' "$ORBJS" | grep -Fq 'owui-border-beam-v1' || {
  echo "ORB_BEAM_REINTRO=FAIL beam_marker"
  exit 2
}
printf '%s' "$ORBCSS" | grep -Fq 'continuity-landing-hero-150-v20260930.1' || {
  echo "ORB_BEAM_REINTRO=FAIL hero_150_marker"
  exit 2
}
printf '%s' "$VOICE" | grep -Fq "1.3.4-nowarm" || {
  echo "ORB_BEAM_REINTRO=FAIL voice_boundary"
  exit 2
}

echo "ORB_BEAM_REINTRO=PUBLIC_PASS"
echo "orb_source_version=1.4.5"
echo "landing_hero_scale=1.5"
echo "active_chat_geometry=UNCHANGED_V1.4.5"
echo "ui_voice_layer=PRESERVED"
echo "stock_loader_bytes=$loader"
echo "stock_custom_css_bytes=$custom"
echo "rollback=$BACKUP"
echo "NEXT=DEVICE_TEST_LANDING_THEN_ACTIVE_CHAT"
