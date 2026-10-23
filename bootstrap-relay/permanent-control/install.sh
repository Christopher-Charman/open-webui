#!/bin/sh
set -eu
umask 077

ACCOUNT="${PPC_ACCOUNT:-${HOME}}"
WEBAPP="$ACCOUNT/webapp"
HTDOCS="$ACCOUNT/htdocs"
STATE="$ACCOUNT/.powerpc-control-v1"
BIN="$WEBAPP/bin/powerpc-control"
DELEGATE="$WEBAPP/bin/delegate-cagent"
VERIFY_DELEGATION="$WEBAPP/bin/verify-continuity-delegation"
DELEGATION_STATE="$ACCOUNT/.continuity-delegation"
DELEGATION_ACCEPTANCE="$DELEGATION_STATE/CONTINUITY_AGENT_DELEGATION_ACCEPTANCE_20261001.json"
PIN="d1ca2801e72e39b502095209683e06fa177067b8"
BASE="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/permanent-control"
TAILSCALE_BASE="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/gateway-tailscale"
TAILSCALE_SERVICE="$WEBAPP/bin/tailscale-service"

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

mkdir -p "$STATE" "$DELEGATION_STATE" "$HTDOCS/.well-known/powerpc-control-v1/results" "$WEBAPP/bin"
chmod 700 "$STATE" "$DELEGATION_STATE"

curl -fsSL --retry 4 "$BASE/daemon.py" -o "$STATE/daemon.py"
curl -fsSL --retry 4 "$BASE/local-mcp-call.mjs" -o "$STATE/local-mcp-call.mjs"
curl -fsSL --retry 4 "$BASE/powerpc-control-service" -o "$BIN"
curl -fsSL --retry 4 "$TAILSCALE_BASE/tailscale-service" -o "$TAILSCALE_SERVICE"
curl -fsSL --retry 4 "$BASE/delegate-cagent.py" -o "$DELEGATE"
curl -fsSL --retry 4 "$BASE/verify-continuity-delegation.py" -o "$VERIFY_DELEGATION"
curl -fsSL --retry 4 "$BASE/CONTINUITY_AGENT_DELEGATION_ACCEPTANCE_20261001.json" -o "$DELEGATION_ACCEPTANCE"
chmod 700 "$STATE/daemon.py" "$STATE/local-mcp-call.mjs" "$BIN" "$TAILSCALE_SERVICE" "$DELEGATE" "$VERIFY_DELEGATION"
chmod 600 "$DELEGATION_ACCEPTANCE"

"$PY" -m py_compile "$STATE/daemon.py" "$DELEGATE" "$VERIFY_DELEGATION"
"$PY" "$DELEGATE" --self-test
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
    echo "delegation_adapter=$DELEGATE"
    echo "delegation_verifier=$VERIFY_DELEGATION"
    echo "delegation_acceptance=$DELEGATION_ACCEPTANCE"
    exit 0
  fi
  sleep 1
done

echo "POWERPC_CONTROL_V1=FAIL" >&2
tail -n 80 "$STATE/service.log" "$STATE/daemon.log" 2>/dev/null || true
exit 1
