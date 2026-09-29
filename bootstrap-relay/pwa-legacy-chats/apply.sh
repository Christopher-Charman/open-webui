#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
TARGET="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui/frontend/index.html"
RESTART="$BASE/restart-openwebui-via-passenger.sh"
PIN="4ab9c2a377fb40a20e83e382c7df765cefb1e6a7"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/pwa-legacy-chats/install.py"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

curl -fsSL --retry 3 --connect-timeout 10 "$RAW" -o "$TMP"
python3 "$TMP"

grep -Fq 'owui-pwa-legacy-chats-bypass-v20260929.5' "$TARGET" || {
  echo "PWA_BYPASS=FAIL marker_missing"
  exit 2
}

test -x "$RESTART" || {
  echo "PWA_BYPASS=FAIL restart_script_missing"
  exit 2
}

"$RESTART"

code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:18080/health || true)"
[ "$code" = "200" ] || {
  echo "PWA_BYPASS=FAIL local_health_http=$code"
  exit 2
}

echo "PWA_BYPASS=HOST_PASS"
echo "marker=owui-pwa-legacy-chats-bypass-v20260929.5"
echo "local_health_http=$code"
echo "NEXT=DEVICE_FORCE_CLOSE_REOPEN_EXISTING_HOME_SCREEN_PWA"
