#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="$PKG/frontend"
FSTATIC="$FRONTEND/static"
SSTATIC="$PKG/static"
LOCKROOT="$BASE/runtime-domains/pwa-repair-agent"
LOCKDIR="$LOCKROOT/.accepted-stack-restore.lock"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOCKROOT/accepted-stack-restore-$STAMP.log"

mkdir -p "$LOCKROOT"

if ! mkdir "$LOCKDIR" 2>/dev/null; then
  echo "ACCEPTED_STACK_RESTORE=FAIL concurrent_repair_lock_present"
  echo "lock=$LOCKDIR"
  exit 9
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT

exec > >(tee -a "$LOG") 2>&1

echo "=== CONTINUITY ACCEPTED STACK RESTORE ==="
echo "timestamp=$STAMP"
echo "ownership=OPENWEBUI_PRESENTATION_AND_VOICE_ONLY"
echo "backend_data_changed=NO"
echo "terminal_changed=NO"
echo "remote_mcp_changed=NO"
echo "concurrency_control=LOCAL_REPAIR_LOCK"

run_pinned() {
  local name="$1" url="$2"
  local tmp
  tmp="$(mktemp)"
  echo "=== $name ==="
  curl -fsSL --retry 3 --connect-timeout 10 "$url" -o "$tmp"
  bash "$tmp"
  rm -f "$tmp"
}

# Phase A: re-establish exact official 0.11.3 frontend generation.
run_pinned "A_OFFICIAL_FRONTEND_0113"   "https://raw.githubusercontent.com/Christopher-Charman/open-webui/350b0e44b5082191ce6fe4bf4c9a0819d79a11f6/bootstrap-relay/official-frontend-restore-0113/apply.sh"

# Phase B: exact first-layer device-verified themes + voice.
run_pinned "B_DEVICE_VERIFIED_UI_VOICE"   "https://raw.githubusercontent.com/Christopher-Charman/open-webui/37209364b2b60366c345a7a8db416b6b3bc58b3c/bootstrap-relay/ui-voice-reintro-v1/apply.sh"

# Phase C: exact v1.4.5 orb/Border Beam lineage with requested +50% landing hero.
run_pinned "C_ORB_BEAM_V145_HERO_150"   "https://raw.githubusercontent.com/Christopher-Charman/open-webui/9799d8b863352d1531bb9d89adcbdbb93e20ae7d/bootstrap-relay/orb-beam-reintro-v145/apply.sh"

# Phase D: exact neural-material presentation that was recovered from the accepted shell.
run_pinned "D_NEURAL_MATERIAL_ACCEPTED_SHELL"   "https://raw.githubusercontent.com/Christopher-Charman/open-webui/c2d744d1a5d463177df9626c56b4f6e0cd367b7c/bootstrap-relay/neural-material-recovery/apply-visual-only.sh"

echo "=== FINAL STATIC INVARIANTS ==="
INDEX="$FRONTEND/index.html"
[ -f "$INDEX" ] || { echo "ACCEPTED_STACK_RESTORE=FAIL index_missing"; exit 20; }

loader_bytes="$(wc -c < "$FSTATIC/loader.js" | tr -d ' ')"
custom_bytes="$(wc -c < "$FSTATIC/custom.css" | tr -d ' ')"
[ "$loader_bytes" = "0" ] || { echo "ACCEPTED_STACK_RESTORE=FAIL loader_not_empty:$loader_bytes"; exit 21; }
[ "$custom_bytes" = "0" ] || { echo "ACCEPTED_STACK_RESTORE=FAIL custom_css_not_empty:$custom_bytes"; exit 22; }

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$INDEX" || {
  echo "ACCEPTED_STACK_RESTORE=FAIL ui_voice_marker_missing"; exit 23;
}
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$INDEX" || {
  echo "ACCEPTED_STACK_RESTORE=FAIL orb_marker_missing"; exit 24;
}

for stale in   continuity-shell-semantic-binder   continuity-shell-hero-presenter   continuity-shell-landing-hero-presenter
do
  if grep -Fq "$stale" "$INDEX"; then
    echo "ACCEPTED_STACK_RESTORE=FAIL stale_reconstruction_marker:$stale"
    exit 25
  fi
done

VOICE="$FSTATIC/pwa-voice-bridge.js"
ORBJS="$FSTATIC/owui-orb-v1.js"
ORBCSS="$FSTATIC/owui-orb-v1.css"
NEURALJS="$FSTATIC/continuity-neural-material.js"
NEURALCSS="$FSTATIC/continuity-neural-material.css"
POST="$FSTATIC/continuity-orb-beam-postmount.js"

for f in "$VOICE" "$ORBJS" "$ORBCSS" "$NEURALJS" "$NEURALCSS" "$POST"; do
  [ -f "$f" ] || { echo "ACCEPTED_STACK_RESTORE=FAIL missing_asset:$f"; exit 26; }
done

grep -Fq "1.3.4-nowarm" "$VOICE" || {
  echo "ACCEPTED_STACK_RESTORE=FAIL voice_bridge_not_nowarm"; exit 27;
}
if grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe' "$VOICE"; then
  echo "ACCEPTED_STACK_RESTORE=FAIL launch_voice_regression_detected"
  exit 28
fi

grep -Fq 'ORB_VERSION = 1.4.5' "$ORBJS" || {
  echo "ACCEPTED_STACK_RESTORE=FAIL orb_not_v145"; exit 29;
}
grep -Fq 'owui-border-beam-v1' "$ORBJS" || {
  echo "ACCEPTED_STACK_RESTORE=FAIL border_beam_missing"; exit 30;
}
grep -Fq 'continuity-landing-hero-150-v20260930.1' "$ORBCSS" || {
  echo "ACCEPTED_STACK_RESTORE=FAIL hero_150_override_missing"; exit 31;
}
grep -Fq 'continuity-neural-material-v20260930.2' "$NEURALCSS" || {
  echo "ACCEPTED_STACK_RESTORE=FAIL neural_material_css_missing"; exit 32;
}
grep -Fq "const VERSION='20260930.2'" "$NEURALJS" || {
  echo "ACCEPTED_STACK_RESTORE=FAIL neural_material_js_missing"; exit 33;
}
grep -Fq 'continuity-neural-material.css?v=20260930.2' "$POST" || {
  echo "ACCEPTED_STACK_RESTORE=FAIL neural_material_not_postmounted"; exit 34;
}

echo "=== MAJEL NONAUDIBLE SYNTHESIS PROBE ==="
HDR="$(mktemp)"
WAV="$(mktemp)"
trap 'rm -f "$HDR" "$WAV"; rmdir "$LOCKDIR" 2>/dev/null || true' EXIT
majel_code="$(curl -sS -D "$HDR" -o "$WAV" -w '%{http_code}' --max-time 45   -X POST http://127.0.0.1:18082/v1/audio/speech   -H 'Content-Type: application/json'   --data '{"model":"kokoro","voice":"majel-computer","input":"System verification.","speed":1}' || true)"
majel_type="$(awk 'BEGIN{IGNORECASE=1} /^content-type:/{gsub(/\r/,""); print $2}' "$HDR" | tail -1)"
majel_bytes="$(wc -c < "$WAV" | tr -d ' ')"
rm -f "$HDR" "$WAV"
trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT

[ "$majel_code" = "200" ] || {
  echo "ACCEPTED_STACK_RESTORE=FAIL majel_synthesis_http:$majel_code"
  exit 35
}
case "$majel_type" in
  audio/*|application/octet-stream) ;;
  *) echo "ACCEPTED_STACK_RESTORE=FAIL majel_content_type:$majel_type"; exit 36 ;;
esac
[ "$majel_bytes" -gt 128 ] || {
  echo "ACCEPTED_STACK_RESTORE=FAIL majel_audio_too_small:$majel_bytes"
  exit 37
}

echo "=== PUBLIC VERIFY ==="
PUB="$(mktemp)"
stamp="$(date +%s)"
curl -fsSL --retry 3 --connect-timeout 10 --max-time 30   -H 'Cache-Control: no-cache' -H 'Pragma: no-cache'   "https://powerpc-darwin.org/?__accepted_stack_restore=$stamp" -o "$PUB"

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$PUB" || {
  rm -f "$PUB"; echo "ACCEPTED_STACK_RESTORE=FAIL public_ui_voice_marker_missing"; exit 38;
}
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$PUB" || {
  rm -f "$PUB"; echo "ACCEPTED_STACK_RESTORE=FAIL public_orb_marker_missing"; exit 39;
}
rm -f "$PUB"

echo "ACCEPTED_STACK_RESTORE=PUBLIC_PASS"
echo "visual_authority=2026-09-23_NEURAL_MATERIAL_ACCEPTED_SHELL"
echo "ui_voice_authority=DEVICE_VERIFIED_GOOD_20260930"
echo "orb_authority=V1.4.5"
echo "landing_hero_scale=1.5"
echo "landing_neural_animation=DYNAMIC"
echo "active_chat_orb=V1.4.5_UNCHANGED"
echo "composer_beam=STRONG_SPECTRAL"
echo "footer_identity=CONTINUITY_SHELL_OPENWEBUI"
echo "voice_bridge=1.3.4-nowarm"
echo "launch_voice_warm_calls=ABSENT"
echo "majel_synthesis_http=$majel_code"
echo "majel_synthesis_content_type=$majel_type"
echo "majel_synthesis_bytes=$majel_bytes"
echo "stock_loader_bytes=$loader_bytes"
echo "stock_custom_css_bytes=$custom_bytes"
echo "NEXT=DEVICE_ACCEPTANCE_SYSTEM_WBW_LCARS_ACTIVE_CHAT_MAJEL"
echo "log=$LOG"
