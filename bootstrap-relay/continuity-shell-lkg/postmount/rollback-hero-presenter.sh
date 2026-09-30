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
[ -n "$BASE" ] || { echo "HERO_PRESENTER_ROLLBACK=FAIL base_unresolved"; exit 2; }
BASE="$(cd "$BASE" && pwd -P)"

PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="$PKG/frontend"
INDEX="$FRONTEND/index.html"
STATIC_A="$PKG/static"
STATIC_B="$FRONTEND/static"
JS_NAME="continuity-shell-hero-presenter.js"
CSS_NAME="continuity-shell-hero-presenter.css"
VOICE="$STATIC_A/pwa-voice-bridge.js"
VOICE_AUTH="5e6d66aaef727ac3da75791c1ef411577ece1ab4573c82a752cc75315a97d140"

BACKUP="$(find "$BASE/runtime-domains/pwa-repair-agent/backups" -maxdepth 1 -type d -name 'pre-landing-hero-presenter-*' -print 2>/dev/null | sort | tail -1)"
[ -n "$BACKUP" ] || { echo "HERO_PRESENTER_ROLLBACK=FAIL backup_missing"; exit 2; }
[ -f "$BACKUP/index.html" ] || { echo "HERO_PRESENTER_ROLLBACK=FAIL backup_index_missing"; exit 2; }

echo "HERO_PRESENTER_ROLLBACK=BEGIN"
echo "source_backup=$BACKUP"

cp -p "$BACKUP/index.html" "$INDEX"

for root in "$STATIC_A" "$STATIC_B"; do
  for n in "$JS_NAME" "$CSS_NAME"; do
    saved="$BACKUP$(dirname "$root/$n")/$n"
    if [ -f "$saved" ]; then
      cp -p "$saved" "$root/$n"
    else
      rm -f "$root/$n"
    fi
  done
done

[ "$(wc -c < "$STATIC_A/loader.js" | tr -d ' ')" = "0" ] || { echo "HERO_PRESENTER_ROLLBACK=FAIL loader_changed"; exit 3; }
[ "$(wc -c < "$STATIC_A/custom.css" | tr -d ' ')" = "0" ] || { echo "HERO_PRESENTER_ROLLBACK=FAIL custom_css_changed"; exit 3; }
[ "$(sha256sum "$VOICE" | awk '{print $1}')" = "$VOICE_AUTH" ] || { echo "HERO_PRESENTER_ROLLBACK=FAIL voice_changed"; exit 3; }
grep -Fq '1.3.4-nowarm' "$VOICE" || { echo "HERO_PRESENTER_ROLLBACK=FAIL voice_nowarm_missing"; exit 3; }
grep -Fq 'continuity-shell-semantic-binder-v20260930.2' "$INDEX" || { echo "HERO_PRESENTER_ROLLBACK=FAIL binder_v2_lost"; exit 3; }

echo "HERO_PRESENTER_ROLLBACK=PASS"
echo "semantic_binder_v2=PRESERVED"
echo "voice_bridge=1.3.4-nowarm"
echo "passenger_restart=NONE"
