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
[ -n "$BASE" ] || { echo "HERO_PRESENTER=FAIL base_unresolved"; exit 2; }
BASE="$(cd "$BASE" && pwd -P)"
echo "BASE_RESOLVED=$BASE"

PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="$PKG/frontend"
INDEX="$FRONTEND/index.html"
STATIC_A="$PKG/static"
STATIC_B="$FRONTEND/static"
VOICE="$STATIC_A/pwa-voice-bridge.js"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BASE/runtime-domains/pwa-repair-agent/backups/pre-landing-hero-presenter-$STAMP"

VERSION="20260930.3"
MARKER="continuity-shell-landing-hero-presenter-v$VERSION"
ASSET_PIN="1c70650d38d34f34b04e42b37971c8d4c367ec43"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$ASSET_PIN/bootstrap-relay/continuity-shell-lkg/postmount"
JS_NAME="continuity-shell-hero-presenter.js"
CSS_NAME="continuity-shell-hero-presenter.css"
VOICE_AUTH="5e6d66aaef727ac3da75791c1ef411577ece1ab4573c82a752cc75315a97d140"

fail(){ echo "HERO_PRESENTER=FAIL $*"; exit 3; }

[ -f "$INDEX" ] || fail index_missing
mkdir -p "$STATIC_A" "$STATIC_B" "$BACKUP"

# Hard invariants from accepted PWA/audio recovery.
[ "$(wc -c < "$STATIC_A/loader.js" | tr -d ' ')" = "0" ] || fail stock_loader_not_empty
[ "$(wc -c < "$STATIC_A/custom.css" | tr -d ' ')" = "0" ] || fail stock_custom_css_not_empty
[ -f "$VOICE" ] || fail voice_bridge_missing
[ "$(sha256sum "$VOICE" | awk '{print $1}')" = "$VOICE_AUTH" ] || fail voice_bridge_hash_changed
grep -Fq '1.3.4-nowarm' "$VOICE" || fail voice_nowarm_marker_missing
if grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe' "$VOICE"; then
  fail voice_warm_path_regressed
fi
grep -Fq 'continuity-shell-semantic-binder-v20260930.2' "$INDEX" || fail semantic_binder_v2_missing

PROTECTED="$BACKUP/protected.before"
: > "$PROTECTED"
for p in   "$STATIC_A/loader.js"   "$STATIC_A/custom.css"   "$STATIC_A/pwa-voice-bridge.js"   "$STATIC_A/pwa-client-runtime.js"   "$STATIC_A/continuity-shell-semantic-binder.js"   "$STATIC_A/continuity-shell-semantic-binder.css"
do
  if [ -f "$p" ]; then
    printf '%s  %s\n' "$(sha256sum "$p" | awk '{print $1}')" "$p" >> "$PROTECTED"
  else
    printf 'ABSENT  %s\n' "$p" >> "$PROTECTED"
  fi
done

cp -p "$INDEX" "$BACKUP/index.html"
for root in "$STATIC_A" "$STATIC_B"; do
  for n in "$JS_NAME" "$CSS_NAME"; do
    if [ -f "$root/$n" ]; then
      mkdir -p "$BACKUP$(dirname "$root/$n")"
      cp -p "$root/$n" "$BACKUP$(dirname "$root/$n")/$n" || true
    fi
  done
done

rollback(){
  echo "=== AUTO ROLLBACK LANDING HERO PRESENTER ==="
  cp -p "$BACKUP/index.html" "$INDEX" || true
  for root in "$STATIC_A" "$STATIC_B"; do
    for n in "$JS_NAME" "$CSS_NAME"; do
      if [ -f "$BACKUP$(dirname "$root/$n")/$n" ]; then
        cp -p "$BACKUP$(dirname "$root/$n")/$n" "$root/$n" || true
      else
        rm -f "$root/$n" || true
      fi
    done
  done
  echo "HERO_PRESENTER=ROLLBACK_AUTO_RESTORED"
}

TMP="$(mktemp -d)"
trap 'rc=$?; rm -rf "$TMP"; if [ $rc -ne 0 ]; then rollback; fi; exit $rc' EXIT

curl -fsSL --retry 3 --connect-timeout 10 "$RAW/$JS_NAME" -o "$TMP/$JS_NAME"
curl -fsSL --retry 3 --connect-timeout 10 "$RAW/$CSS_NAME" -o "$TMP/$CSS_NAME"

NODE="$BASE/.local/node22-glibc217/bin/node"
[ -x "$NODE" ] || NODE="$BASE/.local/node22-el7/bin/node"
[ -x "$NODE" ] || NODE="$(command -v node || true)"
[ -n "$NODE" ] || fail node_missing
"$NODE" --check "$TMP/$JS_NAME" >/dev/null || fail presenter_js_syntax

grep -Fq "const VERSION='20260930.3-landing'" "$TMP/$JS_NAME" || fail presenter_version_missing
grep -Fq 'Landing presentation only: one neural hero + one READY label.' "$TMP/$CSS_NAME" || fail presenter_css_marker_missing
if grep -Eqi '/api/v1/audio/local-voice/warm|warmSelectedVoice|pwa-client-runtime|speechSynthesis|AudioContext|webkitAudioContext'   "$TMP/$JS_NAME" "$TMP/$CSS_NAME"; then
  fail forbidden_runtime_coupling
fi

install -m 0644 "$TMP/$JS_NAME" "$STATIC_A/$JS_NAME"
install -m 0644 "$TMP/$CSS_NAME" "$STATIC_A/$CSS_NAME"
install -m 0644 "$TMP/$JS_NAME" "$STATIC_B/$JS_NAME"
install -m 0644 "$TMP/$CSS_NAME" "$STATIC_B/$CSS_NAME"

python3 - "$INDEX" "$MARKER" "$VERSION" <<'PY'
from pathlib import Path
import re, sys
p=Path(sys.argv[1]); marker=sys.argv[2]; version=sys.argv[3]
s=p.read_text()
pat=re.compile(
    r'\n?<!-- continuity-shell-landing-hero-presenter-v[0-9.]+ -->.*?'
    r'<!-- /continuity-shell-landing-hero-presenter-v[0-9.]+ -->\n?',
    re.S
)
s,n=pat.subn('\n',s)
block=f"""
<!-- {marker} -->
<link rel="stylesheet" href="/static/continuity-shell-hero-presenter.css?v={version}">
<script defer src="/static/continuity-shell-hero-presenter.js?v={version}"></script>
<!-- /{marker} -->
"""
if '</body>' not in s:
    raise SystemExit('HERO_PRESENTER=FAIL closing_body_missing')
p.write_text(s.replace('</body>',block+'\n</body>',1))
print(f"INDEX_HERO_BLOCKS_REMOVED={n}")
print("INDEX_HERO_MARKER=INSTALLED")
PY

# No protected runtime/loader/audio asset may have moved.
while read -r before p; do
  if [ -f "$p" ]; then after="$(sha256sum "$p" | awk '{print $1}')"; else after="ABSENT"; fi
  [ "$before" = "$after" ] || fail "protected_asset_changed:$p"
done < "$PROTECTED"

# Static publication does not require a Passenger restart; avoid concurrent-session process mutation.
PUB="$TMP/public.html"
code="$(curl -sS -o "$PUB" -w '%{http_code}' --max-time 15 -H 'Cache-Control: no-cache'   "https://powerpc-darwin.org/?__hero_presenter=$(date +%s)" || true)"
echo "PUBLIC_HTTP=$code"
[ "$code" = "200" ] || fail public_http

grep -Fq "$MARKER" "$PUB" || fail public_marker_missing

PUBJS="$(curl -fsSL --max-time 15 "https://powerpc-darwin.org/static/$JS_NAME?cb=$(date +%s)")"
PUBCSS="$(curl -fsSL --max-time 15 "https://powerpc-darwin.org/static/$CSS_NAME?cb=$(date +%s)")"
printf '%s' "$PUBJS" | grep -Fq "const VERSION='20260930.3-landing'" || fail public_js_wrong
printf '%s' "$PUBCSS" | grep -Fq 'Landing presentation only: one neural hero + one READY label.' || fail public_css_wrong

VOICE2="$(curl -fsSL --max-time 15 "https://powerpc-darwin.org/static/pwa-voice-bridge.js?cb=$(date +%s)")"
printf '%s' "$VOICE2" | grep -Fq '1.3.4-nowarm' || fail public_voice_changed
if printf '%s' "$VOICE2" | grep -Eq 'warmSelectedVoice|/api/v1/audio/local-voice/warm|observer\.observe'; then
  fail public_voice_warm_path_regressed
fi

loader="$(curl -fsSL --max-time 15 "https://powerpc-darwin.org/static/loader.js?cb=$(date +%s)" | wc -c | tr -d ' ')"
custom="$(curl -fsSL --max-time 15 "https://powerpc-darwin.org/static/custom.css?cb=$(date +%s)" | wc -c | tr -d ' ')"
[ "$loader" = "0" ] || fail public_loader_changed
[ "$custom" = "0" ] || fail public_custom_css_changed

trap - EXIT
rm -rf "$TMP"

echo "HERO_PRESENTER=PUBLIC_PASS"
echo "scope=LANDING_HERO_PLUS_READY_ONLY"
echo "geometry=DYNAMIC_COMPOSER_RELATIVE_NO_LAYOUT_SHIFT"
echo "legacy_ready=SUPPRESSED_NOT_DUPLICATED"
echo "legacy_hero=SUPPRESSED_NOT_DUPLICATED"
echo "footer=REWRITE_EXISTING_ONLY"
echo "chat_telemetry=UNCHANGED"
echo "audio_changes=NONE"
echo "voice_bridge=1.3.4-nowarm"
echo "client_model_runtime=ABSENT"
echo "stock_loader_bytes=$loader"
echo "stock_custom_css_bytes=$custom"
echo "passenger_restart=NONE"
echo "rollback=$BACKUP"
echo "NEXT=DEVICE_TEST_SYSTEM_WBW_LCARS_LANDING"
