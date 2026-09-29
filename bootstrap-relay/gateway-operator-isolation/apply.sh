#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

PIN="4ca5cb2ff0656d6a0f1040bbd478020910b2dc80"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/gateway-operator-isolation/patch.py"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

curl -fsSL --retry 3 --connect-timeout 10 "$RAW" -o "$TMP"
python3 "$TMP"

grep -Fq 'OPENWEBUI_GATEWAY_OPERATOR_PATH_ISOLATION_V1'   /home/storage/781/4477781/user/webapp/passenger_wsgi.py || {
    echo "GATEWAY_ISOLATION=FAIL marker_missing_after_stage"
    exit 2
  }

echo "GATEWAY_ISOLATION=STAGE_COMPLETE"
echo "NEXT=FASTHOSTS_WEB_APPS_RESTART_ONCE"
echo "THEN=FORCE_CLOSE_AND_REOPEN_SAFARI_AND_HOME_SCREEN_PWA"
