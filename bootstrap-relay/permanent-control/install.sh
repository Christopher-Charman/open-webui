#!/bin/sh
set -eu
umask 077

ACCOUNT="/home/storage/781/4477781/user"
WEBAPP="$ACCOUNT/webapp"
HTDOCS="$ACCOUNT/htdocs"
STATE="$ACCOUNT/.powerpc-control-v1"
BIN="$WEBAPP/bin/powerpc-control"
PIN="d0566fe455113a87065c0602974240ece5293a0b"
BASE="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/permanent-control"

[ "$(id -u)" = "2257347" ] || { echo "REFUSED unexpected uid=$(id -u)" >&2; exit 2; }
[ -d "$WEBAPP" ] && [ -d "$HTDOCS" ] || { echo "REFUSED canonical runtime paths missing" >&2; exit 2; }
[ -x "$WEBAPP/bin/local-mcp" ] || { echo "REFUSED local MCP missing" >&2; exit 2; }
[ -x "$WEBAPP/.local/node22-glibc217/bin/node" ] || { echo "REFUSED Node22 missing" >&2; exit 2; }

PY=""
for p in "$WEBAPP/miniconda/bin/python3.12" "$WEBAPP/miniconda/bin/python3" "$WEBAPP/envs/open-terminal/bin/python"; do
  if [ -x "$p" ]; then PY="$p"; break; fi
done
[ -n "$PY" ] || { echo "REFUSED Python missing" >&2; exit 2; }
"$PY" -c 'import cryptography,sqlite3' >/dev/null 2>&1 || { echo "REFUSED cryptography/sqlite unavailable" >&2; exit 2; }

mkdir -p "$STATE" "$HTDOCS/.well-known/powerpc-control-v1/results" "$WEBAPP/bin"
chmod 700 "$STATE"

curl -fsSL --retry 4 "$BASE/daemon.py" -o "$STATE/daemon.py"
curl -fsSL --retry 4 "$BASE/local-mcp-call.mjs" -o "$STATE/local-mcp-call.mjs"
curl -fsSL --retry 4 "$BASE/powerpc-control-service" -o "$BIN"
chmod 700 "$STATE/daemon.py" "$STATE/local-mcp-call.mjs" "$BIN"

"$PY" -m py_compile "$STATE/daemon.py"
"$WEBAPP/.local/node22-glibc217/bin/node" --check "$STATE/local-mcp-call.mjs"

MARK="# POWERPC_CONTROL_V1"
TMP="$STATE/crontab.$$"
(crontab -l 2>/dev/null || true) | awk -v m="$MARK" '$0 !~ m {print}' >"$TMP"
printf '%s\n' "@reboot $BIN ensure >/dev/null 2>&1 $MARK" "* * * * * $BIN ensure >/dev/null 2>&1 $MARK" >>"$TMP"
crontab "$TMP"
rm -f "$TMP"

"$BIN" ensure

IDENTITY="$HTDOCS/.well-known/powerpc-control-v1/identity.json"
STATUS="$HTDOCS/.well-known/powerpc-control-v1/status.json"
deadline=$(( $(date +%s) + 25 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  if [ -s "$IDENTITY" ] && [ -s "$STATUS" ] && "$BIN" status >/dev/null 2>&1; then
    fp="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["identity_fingerprint"])' "$IDENTITY")"
    echo "POWERPC_CONTROL_V1=READY"
    echo "identity_fingerprint=$fp"
    echo "identity_url=https://www.powerpc-darwin.org/.well-known/powerpc-control-v1/identity.json"
    echo "status_url=https://www.powerpc-darwin.org/.well-known/powerpc-control-v1/status.json"
    echo "transport=GITHUB_ENCRYPTED_QUEUE"
    echo "supervision=CRON_ENSURE_DETACHED"
    exit 0
  fi
  sleep 1
done

echo "POWERPC_CONTROL_V1=FAIL" >&2
tail -n 80 "$STATE/service.log" "$STATE/daemon.log" 2>/dev/null || true
exit 1
