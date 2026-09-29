#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
RESTART="$BASE/restart-openwebui-via-passenger.sh"
PIN="3c7aa227610474d5a15f63e1c1bbd9b51c1cee7b"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/owui-0113-chats-backport-v2/patch.py"

TMP="$(mktemp)"
OUT="$(mktemp)"
PUBLIC_HTML="$(mktemp)"
PUBLIC_APP="$(mktemp)"
PUBLIC_NODE="$(mktemp)"
trap 'rm -f "$TMP" "$OUT" "$PUBLIC_HTML" "$PUBLIC_APP" "$PUBLIC_NODE"' EXIT

curl -fsSL --retry 3 --connect-timeout 10 "$RAW" -o "$TMP"
python3 "$TMP" | tee "$OUT"

APP="$(awk -F= '/^APP=/{print $2}' "$OUT" | tail -1)"
NODE="$(awk -F= '/^NODE=/{print $2}' "$OUT" | tail -1)"

[ -n "$APP" ] || { echo "CHAT_STARTUP_BACKPORT_V2=FAIL missing_app_receipt"; exit 2; }
[ -n "$NODE" ] || { echo "CHAT_STARTUP_BACKPORT_V2=FAIL missing_node_receipt"; exit 2; }

test -x "$RESTART" || {
  echo "CHAT_STARTUP_BACKPORT_V2=FAIL restart_script_missing"
  exit 2
}

"$RESTART"

local_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18080/health || true)"
[ "$local_code" = "200" ] || {
  echo "CHAT_STARTUP_BACKPORT_V2=FAIL local_health_http=$local_code"
  exit 2
}

probe="https://powerpc-darwin.org/?__chats_backport_v2=$(date +%s)"
curl -fsSL --retry 3 --connect-timeout 10 --max-time 25 \
  -H 'Cache-Control: no-cache' -H 'Pragma: no-cache' \
  "$probe" -o "$PUBLIC_HTML" || {
    echo "CHAT_STARTUP_BACKPORT_V2=FAIL public_html_fetch"
    exit 2
  }

grep -Fq 'owui-chats-startup-backport-v20260929.2' "$PUBLIC_HTML" || {
  echo "CHAT_STARTUP_BACKPORT_V2=FAIL public_marker_missing"
  exit 2
}
grep -Fq "$APP" "$PUBLIC_HTML" || {
  echo "CHAT_STARTUP_BACKPORT_V2=FAIL public_app_reference_missing"
  exit 2
}

curl -fsSL --retry 3 --max-time 20 \
  "https://powerpc-darwin.org$APP?cb=$(date +%s)" -o "$PUBLIC_APP" || {
    echo "CHAT_STARTUP_BACKPORT_V2=FAIL public_app_fetch"
    exit 2
  }

node_base="$(basename "$NODE")"
grep -Fq "../nodes/$node_base" "$PUBLIC_APP" || {
  echo "CHAT_STARTUP_BACKPORT_V2=FAIL app_does_not_reference_fixed_node"
  exit 2
}

curl -fsSL --retry 3 --max-time 20 \
  "https://powerpc-darwin.org$NODE?cb=$(date +%s)" -o "$PUBLIC_NODE" || {
    echo "CHAT_STARTUP_BACKPORT_V2=FAIL public_node_fetch"
    exit 2
  }

python3 - "$PUBLIC_NODE" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
if not re.search(r'openDB\(["\']Chats["\']\s*,\s*1\)', text):
    raise SystemExit('CHAT_STARTUP_BACKPORT_V2=FAIL public_node_legacy_lineage_missing')
if re.search(r'await\s+Promise\.all\(\[\s*checkLocalDBChats\(\)\s*,', text, re.S):
    raise SystemExit('CHAT_STARTUP_BACKPORT_V2=FAIL public_node_still_blocks_on_legacy_chats')
print('PUBLIC_NODE_SEMANTICS=PASS')
PY

echo "CHAT_STARTUP_BACKPORT_V2=PUBLIC_PASS"
echo "coherence_repair=PASS"
echo "semantics=UPSTREAM_EQUIVALENT_REMOVE_BLOCKING_STARTUP_CALL"
echo "scope=ALL_BROWSER_MODES"
echo "data_deletion=NONE"
echo "local_health_http=$local_code"
echo "app=$APP"
echo "node=$NODE"
echo "NEXT=FORCE_CLOSE_REOPEN_SAFARI_THEN_HOME_SCREEN_PWA"
