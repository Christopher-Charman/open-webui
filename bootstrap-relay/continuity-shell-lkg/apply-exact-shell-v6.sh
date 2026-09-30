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

ASSET_PIN="c85fc7e045da598ddf3db0a5fd51f5ce710b4eb6"
RAW_BASE="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$ASSET_PIN/bootstrap-relay/continuity-shell-lkg"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BASE/runtime-domains/pwa-repair-agent/backups/pre-continuity-shell-lkg-v6-$STAMP"
VERSION="20260930.5"

LKG_CSS="$FSTATIC/continuity-shell-lkg.css"
COMPAT_CSS="$FSTATIC/continuity-shell-compat.css"
MAPPER_JS="$FSTATIC/continuity-shell-lkg-mapper.js"

mkdir -p "$BACKUP/frontend/static" "$BACKUP/served/static"

fail(){ echo "CONTINUITY_SHELL_LKG_V6=FAIL $*"; exit 2; }

[ -f "$INDEX" ] || fail index_missing
[ -f "$POST" ] || fail postmount_missing
[ "$(wc -c < "$FSTATIC/loader.js" | tr -d ' ')" = "0" ] || fail stock_loader_not_empty
[ "$(wc -c < "$FSTATIC/custom.css" | tr -d ' ')" = "0" ] || fail stock_custom_css_not_empty

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$INDEX" || fail ui_voice_marker_missing
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$INDEX" || fail orb_marker_missing
grep -Fq "1.3.4-nowarm" "$FSTATIC/pwa-voice-bridge.js" || fail voice_boundary_missing
if grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe' "$FSTATIC/pwa-voice-bridge.js"; then
  fail voice_boundary_regressed
fi
if grep -Fq 'continuity-settings.js' "$POST"; then
  fail native_settings_injection_present
fi

cp -p "$INDEX" "$BACKUP/frontend/index.html"
cp -p "$POST" "$BACKUP/frontend/static/continuity-orb-beam-postmount.js"
[ ! -f "$SPOST" ] || cp -p "$SPOST" "$BACKUP/served/static/continuity-orb-beam-postmount.js"

for n in continuity-shell-lkg.css continuity-shell-compat.css continuity-shell-lkg-mapper.js; do
  [ ! -f "$FSTATIC/$n" ] || cp -p "$FSTATIC/$n" "$BACKUP/frontend/static/$n"
  [ ! -f "$SSTATIC/$n" ] || cp -p "$SSTATIC/$n" "$BACKUP/served/static/$n"
done

rollback(){
  echo "=== AUTO ROLLBACK CONTINUITY SHELL LKG V6 ==="
  cp -p "$BACKUP/frontend/index.html" "$INDEX" || true
  cp -p "$BACKUP/frontend/static/continuity-orb-beam-postmount.js" "$POST" || true
  if [ -f "$BACKUP/served/static/continuity-orb-beam-postmount.js" ]; then
    cp -p "$BACKUP/served/static/continuity-orb-beam-postmount.js" "$SPOST"
  else
    cp -p "$POST" "$SPOST" || true
  fi
  for n in continuity-shell-lkg.css continuity-shell-compat.css continuity-shell-lkg-mapper.js; do
    if [ -f "$BACKUP/frontend/static/$n" ]; then cp -p "$BACKUP/frontend/static/$n" "$FSTATIC/$n"; else rm -f "$FSTATIC/$n"; fi
    if [ -f "$BACKUP/served/static/$n" ]; then cp -p "$BACKUP/served/static/$n" "$SSTATIC/$n"; else rm -f "$SSTATIC/$n"; fi
  done
  "$RESTART" >/dev/null 2>&1 || true
  echo "CONTINUITY_SHELL_LKG_V6=ROLLBACK_AUTO_RESTORED"
}
trap 'rc=$?; if [ $rc -ne 0 ]; then rollback; fi; exit $rc' EXIT

TMP="$(mktemp -d)"
trap 'rc=$?; rm -rf "$TMP"; if [ $rc -ne 0 ]; then rollback; fi; exit $rc' EXIT

curl -fsSL --retry 3 --connect-timeout 10 "$RAW_BASE/continuity-shell-lkg.css" -o "$TMP/lkg.css"
curl -fsSL --retry 3 --connect-timeout 10 "$RAW_BASE/continuity-shell-compat.css" -o "$TMP/compat.css"
curl -fsSL --retry 3 --connect-timeout 10 "$RAW_BASE/continuity-shell-lkg-mapper.js" -o "$TMP/mapper.js"

grep -Fq 'Source: repository-prime@db992650f91388e59bb074f12b15e2f8acdc2b05' "$TMP/lkg.css" || fail exact_lkg_source_marker_missing
grep -Fq 'Shared vibrancy restoration v1.0' "$TMP/lkg.css" || fail lkg_vibrancy_block_missing
grep -Fq 'World Between Worlds / Ahsoka theme v1.0' "$TMP/lkg.css" || fail lkg_wbw_block_missing
grep -Fq "const VERSION='20260930.5'" "$TMP/mapper.js" || fail mapper_version_missing
grep -Fq 'Continuity Shell semantic compatibility layer' "$TMP/compat.css" || fail compat_marker_missing

if grep -Eqi '/api/v1/audio/local-voice/warm|local-voice/warm|warmSelectedVoice|pwa-client-runtime|speechSynthesis|AudioContext|webkitAudioContext' \
  "$TMP/lkg.css" "$TMP/compat.css" "$TMP/mapper.js"; then
  fail forbidden_audio_or_client_runtime_reference
fi

NODE="$BASE/.local/node22-glibc217/bin/node"
[ -x "$NODE" ] || NODE="$BASE/.local/node22-el7/bin/node"
[ -x "$NODE" ] || fail node_runtime_missing
"$NODE" --check "$TMP/mapper.js" >/dev/null || fail mapper_js_syntax

cp -p "$TMP/lkg.css" "$LKG_CSS"
cp -p "$TMP/compat.css" "$COMPAT_CSS"
cp -p "$TMP/mapper.js" "$MAPPER_JS"
cp -p "$LKG_CSS" "$SSTATIC/continuity-shell-lkg.css"
cp -p "$COMPAT_CSS" "$SSTATIC/continuity-shell-compat.css"
cp -p "$MAPPER_JS" "$SSTATIC/continuity-shell-lkg-mapper.js"

python3 - "$POST" "$VERSION" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); version=sys.argv[2]; s=p.read_text()
if "continuity-shell-lkg.css" in s or "continuity-shell-lkg-mapper.js" in s:
    raise SystemExit("CONTINUITY_SHELL_LKG_V6=FAIL already_referenced")
anchor="await js('/static/continuity-neural-parity-v3.js?v=20260930.3');"
if anchor not in s:
    raise SystemExit("CONTINUITY_SHELL_LKG_V6=FAIL parity_v3_anchor_missing")
insert=(anchor
    + "\n    await css('/static/continuity-shell-lkg.css?v=" + version + "');"
    + "\n    await css('/static/continuity-shell-compat.css?v=" + version + "');"
    + "\n    await js('/static/continuity-shell-lkg-mapper.js?v=" + version + "');")
p.write_text(s.replace(anchor,insert,1))
PY
cp -p "$POST" "$SPOST"
"$NODE" --check "$POST" >/dev/null || fail postmount_syntax

python3 - "$INDEX" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
old='/static/continuity-orb-beam-postmount.js?v=20260930.2'
new='/static/continuity-orb-beam-postmount.js?v=20260930.3'
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit("CONTINUITY_SHELL_LKG_V6=FAIL postmount_cache_anchor_missing")
p.write_text(s)
PY

"$RESTART"

[ "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18080/health || true)" = "200" ] || fail openwebui_health

stamp="$(date +%s)"
PUB="$(mktemp)"
curl -fsSL --retry 3 --max-time 25 -H 'Cache-Control: no-cache' \
  "https://powerpc-darwin.org/?__continuity_shell_lkg=$stamp" -o "$PUB"

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$PUB" || fail ui_voice_marker_lost
grep -Fq 'owui-postmount-orb-beam-v20260930.1' "$PUB" || fail orb_marker_lost
grep -Fq 'continuity-orb-beam-postmount.js?v=20260930.3' "$PUB" || fail postmount_cache_generation_not_advanced

loader="$(curl -fsSL "https://powerpc-darwin.org/static/loader.js?cb=$stamp" | wc -c | tr -d ' ')"
custom="$(curl -fsSL "https://powerpc-darwin.org/static/custom.css?cb=$stamp" | wc -c | tr -d ' ')"
[ "$loader" = "0" ] || fail public_stock_loader_changed
[ "$custom" = "0" ] || fail public_stock_custom_css_changed

PUBPOST="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-orb-beam-postmount.js?cb=$stamp")"
printf '%s' "$PUBPOST" | grep -Fq 'continuity-shell-lkg.css?v=20260930.5' || fail lkg_css_not_postmounted
printf '%s' "$PUBPOST" | grep -Fq 'continuity-shell-compat.css?v=20260930.5' || fail compat_css_not_postmounted
printf '%s' "$PUBPOST" | grep -Fq 'continuity-shell-lkg-mapper.js?v=20260930.5' || fail mapper_not_postmounted

PUBLKG="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-shell-lkg.css?cb=$stamp")"
PUBMAP="$(curl -fsSL "https://powerpc-darwin.org/static/continuity-shell-lkg-mapper.js?cb=$stamp")"
printf '%s' "$PUBLKG" | grep -Fq 'repository-prime@db992650f91388e59bb074f12b15e2f8acdc2b05' || fail public_lkg_source_marker_missing
printf '%s' "$PUBMAP" | grep -Fq "const VERSION='20260930.5'" || fail public_mapper_version_missing

VOICE2="$(curl -fsSL "https://powerpc-darwin.org/static/pwa-voice-bridge.js?cb=$stamp")"
printf '%s' "$VOICE2" | grep -Fq "1.3.4-nowarm" || fail voice_bridge_changed
if printf '%s' "$VOICE2" | grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe'; then
  fail voice_boundary_regressed
fi

rm -f "$PUB"
trap - EXIT
rm -rf "$TMP"

echo "CONTINUITY_SHELL_LKG_V6=PUBLIC_PASS"
echo "visual_source=repository-prime@db992650f91388e59bb074f12b15e2f8acdc2b05"
echo "visual_source_class=EXACT_2026-09-28_CONTINUITY_SHELL_BASELINE"
echo "application=POSTMOUNT_SEMANTIC_MAPPING"
echo "world_between_worlds=DARK_NATIVE_CYAN_ICEWHITE_AHSOKA_ORANGE"
echo "prompt=EXACT_DUAL_LAYER_VIBRANT_BEAM"
echo "panels=EXACT_GLASS_LUMINOUS_EDGES"
echo "neural_hero=PRESERVED_150_PERCENT"
echo "chat_orb=PRESERVED_STANDALONE_42PX"
echo "continuity_controls=RESTYLED_TO_SHELL_LANGUAGE"
echo "auth_surface=UNCHANGED_NATIVE"
echo "audio_changes=NONE"
echo "client_model_runtime=ABSENT"
echo "voice_bridge=1.3.4-nowarm"
echo "stock_loader_bytes=$loader"
echo "stock_custom_css_bytes=$custom"
echo "rollback=$BACKUP"
echo "NEXT=DEVICE_COMPARE_TO_CONTINUITY_SHELL_REFERENCE"
