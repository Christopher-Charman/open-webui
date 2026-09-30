#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="$PKG/frontend"
FSTATIC="$FRONTEND/static"
SSTATIC="$PKG/static"
INDEX="$FRONTEND/index.html"
POST="$FSTATIC/continuity-orb-beam-postmount.js"
SPOST="$SSTATIC/continuity-orb-beam-postmount.js"
RESTART="$BASE/restart-openwebui-via-passenger.sh"

fail(){ echo "ROLLBACK_V6_TO_V4=FAIL $*"; exit 2; }

BACKUP="$(find "$BASE/runtime-domains/pwa-repair-agent/backups" -maxdepth 1 -type d -name 'pre-continuity-shell-lkg-v6-*' -print 2>/dev/null | sort | tail -1)"
[ -n "$BACKUP" ] || fail v6_backup_not_found
[ -f "$BACKUP/frontend/index.html" ] || fail backup_index_missing
[ -f "$BACKUP/frontend/static/continuity-orb-beam-postmount.js" ] || fail backup_postmount_missing

echo "ROLLBACK_V6_TO_V4=BEGIN"
echo "source_backup=$BACKUP"

cp -p "$BACKUP/frontend/index.html" "$INDEX"
cp -p "$BACKUP/frontend/static/continuity-orb-beam-postmount.js" "$POST"

if [ -f "$BACKUP/served/static/continuity-orb-beam-postmount.js" ]; then
  cp -p "$BACKUP/served/static/continuity-orb-beam-postmount.js" "$SPOST"
else
  cp -p "$POST" "$SPOST"
fi

for n in continuity-shell-lkg.css continuity-shell-compat.css continuity-shell-lkg-mapper.js; do
  if [ -f "$BACKUP/frontend/static/$n" ]; then
    cp -p "$BACKUP/frontend/static/$n" "$FSTATIC/$n"
  else
    rm -f "$FSTATIC/$n"
  fi
  if [ -f "$BACKUP/served/static/$n" ]; then
    cp -p "$BACKUP/served/static/$n" "$SSTATIC/$n"
  else
    rm -f "$SSTATIC/$n"
  fi
done

# The protected accepted layer must still be present.
grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$INDEX" || fail accepted_ui_voice_marker_missing
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$INDEX" || fail accepted_orb_marker_missing
grep -Fq "1.3.4-nowarm" "$FSTATIC/pwa-voice-bridge.js" || fail voice_bridge_boundary_missing

if grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe' "$FSTATIC/pwa-voice-bridge.js"; then
  fail voice_bridge_regressed
fi

[ "$(wc -c < "$FSTATIC/loader.js" | tr -d ' ')" = "0" ] || fail stock_loader_not_empty
[ "$(wc -c < "$FSTATIC/custom.css" | tr -d ' ')" = "0" ] || fail stock_custom_css_not_empty

"$RESTART"

[ "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18080/health || true)" = "200" ] || fail local_health

stamp="$(date +%s)"
PUB="$(mktemp)"
trap 'rm -f "$PUB"' EXIT

curl -fsSL --retry 3 --max-time 25 -H 'Cache-Control: no-cache' \
  "https://powerpc-darwin.org/?__rollback_v6=$stamp" -o "$PUB"

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$PUB" || fail public_ui_voice_marker_missing
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$PUB" || fail public_orb_marker_missing

if grep -Fq 'continuity-shell-lkg-mapper.js' "$PUB"; then
  fail v6_mapper_still_referenced
fi

loader="$(curl -fsSL "https://powerpc-darwin.org/static/loader.js?cb=$stamp" | wc -c | tr -d ' ')"
custom="$(curl -fsSL "https://powerpc-darwin.org/static/custom.css?cb=$stamp" | wc -c | tr -d ' ')"
[ "$loader" = "0" ] || fail public_loader_changed
[ "$custom" = "0" ] || fail public_custom_css_changed

VOICE="$(curl -fsSL "https://powerpc-darwin.org/static/pwa-voice-bridge.js?cb=$stamp")"
printf '%s' "$VOICE" | grep -Fq "1.3.4-nowarm" || fail public_voice_bridge_wrong
if printf '%s' "$VOICE" | grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe'; then
  fail public_voice_bridge_regressed
fi

echo "ROLLBACK_V6_TO_V4=PUBLIC_PASS"
echo "regressed_layer=CONTINUITY_SHELL_LKG_V6_REMOVED"
echo "accepted_ui_voice_layer=PRESERVED"
echo "voice_bridge=1.3.4-nowarm"
echo "voice_warm_calls=ABSENT"
echo "stock_loader_bytes=$loader"
echo "stock_custom_css_bytes=$custom"
echo "next_test=LAUNCH_AUDIO_THEN_HERO_THEN_CHAT_ORB"
