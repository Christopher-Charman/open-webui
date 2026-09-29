#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
TARGET="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui/frontend/index.html"
RESTART="$BASE/restart-openwebui-via-passenger.sh"
PIN="b661a7bca426c022f004edd5adb96759cd3e0578"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/pwa-legacy-chats/install.py"
TMP="$(mktemp)"
PUBLIC_HTML="$(mktemp)"
PUBLIC_APP="$(mktemp)"
trap 'rm -f "$TMP" "$PUBLIC_HTML" "$PUBLIC_APP"' EXIT

curl -fsSL --retry 3 --connect-timeout 10 "$RAW" -o "$TMP"
python3 "$TMP"

grep -Fq 'owui-pwa-startup-guard-v20260929.6' "$TARGET" || {
  echo "PWA_BYPASS=FAIL marker_missing"
  exit 2
}

APP="$(python3 - <<'PY'
import re
from pathlib import Path
p=Path('/home/storage/781/4477781/user/webapp/envs/openwebui/lib/python3.11/site-packages/open_webui/frontend/index.html')
m=re.search(r'/_app/immutable/entry/app\.[A-Za-z0-9_-]+\.pwa20260929_6\.js', p.read_text())
print(m.group(0) if m else '')
PY
)"
NODE="$(python3 - <<'PY'
import re
from pathlib import Path
p=Path('/home/storage/781/4477781/user/webapp/envs/openwebui/lib/python3.11/site-packages/open_webui/frontend/index.html')
m=re.search(r'/_app/immutable/nodes/2\.[A-Za-z0-9_-]+\.pwa20260929_6\.js', p.read_text())
print(m.group(0) if m else '')
PY
)"

[ -n "$APP" ] || { echo "PWA_BYPASS=FAIL app_url_missing"; exit 2; }
[ -n "$NODE" ] || { echo "PWA_BYPASS=FAIL node_url_missing"; exit 2; }

test -x "$RESTART" || {
  echo "PWA_BYPASS=FAIL restart_script_missing"
  exit 2
}

"$RESTART"

code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18080/health || true)"
[ "$code" = "200" ] || {
  echo "PWA_BYPASS=FAIL local_health_http=$code"
  exit 2
}

probe="https://powerpc-darwin.org/?__owui_pwa_probe=20260929.6-$(date +%s)"
curl -fsSL --retry 3 --connect-timeout 10 --max-time 25 \
  -H 'Cache-Control: no-cache' \
  -H 'Pragma: no-cache' \
  "$probe" -o "$PUBLIC_HTML" || {
    echo "PWA_BYPASS=FAIL public_html_fetch"
    exit 2
  }

grep -Fq 'owui-pwa-startup-guard-v20260929.6' "$PUBLIC_HTML" || {
  echo "PWA_BYPASS=FAIL public_marker_missing"
  exit 2
}
grep -Fq "$APP" "$PUBLIC_HTML" || {
  echo "PWA_BYPASS=FAIL public_app_reference_missing"
  exit 2
}

app_code="$(curl -sS -o "$PUBLIC_APP" -w '%{http_code}' --max-time 15 "https://powerpc-darwin.org$APP?cb=20260929.6" || true)"
[ "$app_code" = "200" ] || {
  echo "PWA_BYPASS=FAIL public_app_http=$app_code"
  exit 2
}
node_base="${NODE##*/}"
grep -Fq "../nodes/$node_base" "$PUBLIC_APP" || {
  echo "PWA_BYPASS=FAIL public_app_missing_node_reference"
  exit 2
}
node_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://powerpc-darwin.org$NODE?cb=20260929.6" || true)"
[ "$node_code" = "200" ] || {
  echo "PWA_BYPASS=FAIL public_node_http=$node_code"
  exit 2
}

echo "PWA_BYPASS=PUBLIC_PASS"
echo "marker=owui-pwa-startup-guard-v20260929.6"
echo "local_health_http=$code"
echo "public_app_http=$app_code"
echo "public_node_http=$node_code"
echo "app=$APP"
echo "node=$NODE"
echo "NEXT=DEVICE_FORCE_CLOSE_REOPEN_EXISTING_HOME_SCREEN_PWA"
