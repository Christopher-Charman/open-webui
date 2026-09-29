#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="$PKG/frontend"
FRONT_STATIC="$FRONTEND/static"
SERVED_STATIC="$PKG/static"
INDEX="$FRONTEND/index.html"
RESTART="$BASE/restart-openwebui-via-passenger.sh"

PIN="3a66488a9efd3502722ce7602b058371f0f5830d"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/ui-voice-reintro-v1/install.py"

TMP="$(mktemp)"
OUT="$(mktemp)"
PUB="$(mktemp)"
trap 'rm -f "$TMP" "$OUT" "$PUB"' EXIT

rollback_layer() {
  local backup="$1"
  [ -n "$backup" ] || return 0
  echo "=== AUTO ROLLBACK UI/VOICE LAYER ==="
  if [ -f "$backup/frontend/index.html" ]; then
    cp -p "$backup/frontend/index.html" "$INDEX"
  fi
  for name in \
    continuity-theme-overlay.css \
    lcars-theme.css \
    lcars-runtime.js \
    continuity-controls.js \
    continuity-shell-registry.js \
    pwa-voice-bridge.js \
    continuity-postmount-bootstrap.js
  do
    if [ -f "$backup/frontend/static/$name" ]; then
      cp -p "$backup/frontend/static/$name" "$FRONT_STATIC/$name"
    else
      rm -f "$FRONT_STATIC/$name"
    fi
    if [ -f "$backup/served/static/$name" ]; then
      cp -p "$backup/served/static/$name" "$SERVED_STATIC/$name"
    else
      rm -f "$SERVED_STATIC/$name"
    fi
  done
  "$RESTART" || true
  echo "UI_VOICE_REINTRO=ROLLBACK_AUTO_RESTORED"
}

echo "=== PRECHECK VOICE BACKENDS; NO WARM/SYNTHESIS ==="
tts_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18082/health || true)"
pocket_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18083/health || true)"
[ "$tts_code" = "200" ] || { echo "UI_VOICE_REINTRO=FAIL tts_health_http=$tts_code"; exit 2; }
[ "$pocket_code" = "200" ] || { echo "UI_VOICE_REINTRO=FAIL pocket_health_http=$pocket_code"; exit 2; }

AUDIO_ROUTER="$PKG/routers/audio.py"
[ -f "$AUDIO_ROUTER" ] || { echo "UI_VOICE_REINTRO=FAIL audio_router_missing"; exit 2; }
grep -Fq 'local-voice/status' "$AUDIO_ROUTER" || { echo "UI_VOICE_REINTRO=FAIL local_voice_status_route_missing"; exit 2; }
grep -Fq 'local-voice/speech' "$AUDIO_ROUTER" || { echo "UI_VOICE_REINTRO=FAIL local_voice_speech_route_missing"; exit 2; }

curl -fsSL --retry 3 --connect-timeout 10 "$RAW" -o "$TMP"
python3 "$TMP" | tee "$OUT"

grep -Fq 'UI_VOICE_REINTRO=STAGED_ON_DISK_PASS' "$OUT" || {
  echo "UI_VOICE_REINTRO=FAIL installer_receipt_missing"
  exit 2
}

BACKUP="$(awk -F= '/^BACKUP=/{print $2}' "$OUT" | tail -1)"
[ -n "$BACKUP" ] || {
  echo "UI_VOICE_REINTRO=FAIL backup_receipt_missing"
  exit 2
}

test -x "$RESTART" || {
  rollback_layer "$BACKUP"
  echo "UI_VOICE_REINTRO=FAIL restart_script_missing"
  exit 2
}

echo "=== RESTART OPENWEBUI ==="
if ! "$RESTART"; then
  rollback_layer "$BACKUP"
  echo "UI_VOICE_REINTRO=FAIL restart_failed"
  exit 2
fi

local_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18080/health || true)"
if [ "$local_code" != "200" ]; then
  rollback_layer "$BACKUP"
  echo "UI_VOICE_REINTRO=FAIL local_health_http=$local_code"
  exit 2
fi

echo "=== PUBLIC VERIFY ==="
stamp="$(date +%s)"
if ! curl -fsSL --retry 3 --connect-timeout 10 --max-time 25 \
  -H 'Cache-Control: no-cache' -H 'Pragma: no-cache' \
  "https://powerpc-darwin.org/?__ui_voice_v1=$stamp" -o "$PUB"
then
  rollback_layer "$BACKUP"
  echo "UI_VOICE_REINTRO=FAIL public_html_fetch"
  exit 2
fi

grep -Fq 'owui-postmount-ui-voice-v20260929.1' "$PUB" || {
  rollback_layer "$BACKUP"
  echo "UI_VOICE_REINTRO=FAIL public_layer_marker_missing"
  exit 2
}

# Stock bootstrap surfaces must remain inert.
loader_bytes="$(curl -fsSL --max-time 15 "https://powerpc-darwin.org/static/loader.js?cb=$stamp" | wc -c | tr -d ' ')"
css_bytes="$(curl -fsSL --max-time 15 "https://powerpc-darwin.org/static/custom.css?cb=$stamp" | wc -c | tr -d ' ')"
if [ "$loader_bytes" != "0" ] || [ "$css_bytes" != "0" ]; then
  rollback_layer "$BACKUP"
  echo "UI_VOICE_REINTRO=FAIL stock_bootstrap_mutated loader=$loader_bytes css=$css_bytes"
  exit 2
fi

# Stock immutable app generation must remain coherent.
python3 - "$PUB" <<'PY'
from pathlib import Path
import re,sys
s=Path(sys.argv[1]).read_text()
p=sorted(set(re.findall(r'/_app/immutable/entry/(app\.[A-Za-z0-9_-]+\.js)',s)))
i=sorted(set(Path(x).name for x in re.findall(r'import\(["\']/(_app/immutable/entry/app\.[A-Za-z0-9_-]+\.js)["\']\)',s)))
if len(p)!=1 or p!=i:
    raise SystemExit("PUBLIC_STOCK_APP_COHERENCE=FAIL preload=%r import=%r"%(p,i))
print("PUBLIC_STOCK_APP_COHERENCE=PASS")
print("PUBLIC_STOCK_APP="+p[0])
PY

check_asset() {
  local path="$1" expect="$2"
  local headers body code ctype
  headers="$(mktemp)"; body="$(mktemp)"
  code="$(curl -sS -D "$headers" -o "$body" -w '%{http_code}' --max-time 20 "https://powerpc-darwin.org/static/$path?cb=$stamp" || true)"
  ctype="$(awk 'BEGIN{IGNORECASE=1} /^content-type:/{gsub(/\r/,""); print $2}' "$headers" | tail -1)"
  rm -f "$headers"
  if [ "$code" != "200" ] || [[ "$ctype" != *"$expect"* ]]; then
    rm -f "$body"
    rollback_layer "$BACKUP"
    echo "UI_VOICE_REINTRO=FAIL asset=$path http=$code content_type=$ctype expected=$expect"
    exit 2
  fi
  printf '%s' "$body"
}

BOOT_BODY="$(check_asset continuity-postmount-bootstrap.js javascript)"
THEME_BODY="$(check_asset continuity-theme-overlay.css css)"
VOICE_BODY="$(check_asset pwa-voice-bridge.js javascript)"
REG_BODY="$(check_asset continuity-shell-registry.js javascript)"
CTRL_BODY="$(check_asset continuity-controls.js javascript)"
LCARS_BODY="$(check_asset lcars-runtime.js javascript)"

grep -Fq "VERSION = '1.3.4-nowarm'" "$VOICE_BODY" || {
  rollback_layer "$BACKUP"; echo "UI_VOICE_REINTRO=FAIL voice_version"; exit 2;
}
if grep -Fq '/api/v1/audio/local-voice/warm' "$VOICE_BODY" || grep -Fq 'warmSelectedVoice' "$VOICE_BODY"; then
  rollback_layer "$BACKUP"; echo "UI_VOICE_REINTRO=FAIL warm_behavior_present"; exit 2;
fi
if grep -Fq 'observer.observe' "$VOICE_BODY"; then
  rollback_layer "$BACKUP"; echo "UI_VOICE_REINTRO=FAIL dangling_observer_present"; exit 2;
fi

grep -Fq "World Between Worlds" "$REG_BODY" || {
  rollback_layer "$BACKUP"; echo "UI_VOICE_REINTRO=FAIL wbw_theme_missing"; exit 2;
}
grep -Fq "LCARS" "$REG_BODY" || {
  rollback_layer "$BACKUP"; echo "UI_VOICE_REINTRO=FAIL lcars_theme_missing"; exit 2;
}
for voice in 'Ahsoka Hybrid' 'Ahsoka Piper (reference)' 'Cortana' 'Majel Computer'; do
  grep -Fq "$voice" "$REG_BODY" || {
    rollback_layer "$BACKUP"; echo "UI_VOICE_REINTRO=FAIL voice_registry_missing=$voice"; exit 2;
  }
done

# Explicitly prove excluded layers are still absent from the document/post-mount bootstrap.
if grep -Fq 'pwa-client-runtime.js' "$PUB" || grep -Fq 'continuity-settings.js' "$PUB" || \
   grep -Fq 'pwa-client-runtime.js' "$BOOT_BODY" || grep -Fq 'continuity-settings.js' "$BOOT_BODY"; then
  rollback_layer "$BACKUP"
  echo "UI_VOICE_REINTRO=FAIL excluded_layer_reference_present"
  exit 2
fi

# Re-check services after restart without warming/synthesizing.
tts_after="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18082/health || true)"
pocket_after="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18083/health || true)"
if [ "$tts_after" != "200" ] || [ "$pocket_after" != "200" ]; then
  rollback_layer "$BACKUP"
  echo "UI_VOICE_REINTRO=FAIL voice_backend_postrestart tts=$tts_after pocket=$pocket_after"
  exit 2
fi

echo "UI_VOICE_REINTRO=PUBLIC_PASS"
echo "layer=POSTMOUNT_THEMES_AND_SERVER_VOICES_ONLY"
echo "themes=System|Dark|OLED Dark|World Between Worlds|LCARS"
echo "voices=Ahsoka Hybrid|Ahsoka Piper (reference)|Cortana|Majel Computer"
echo "voice_bridge=1.3.4-nowarm"
echo "client_model_runtime=ABSENT"
echo "voice_warm_calls=ABSENT"
echo "native_settings_dom_injection=ABSENT"
echo "orb_borderbeam_runtime=DEFERRED_NEXT_LAYER"
echo "stock_loader_bytes=$loader_bytes"
echo "stock_custom_css_bytes=$css_bytes"
echo "tts_health_http=$tts_after"
echo "pocket_health_http=$pocket_after"
echo "rollback=$BACKUP"
echo "NEXT=DEVICE_TEST_SAFARI_THEN_HOME_SCREEN_THEME_SELECTION_AND_VOICE_SELECTION"
