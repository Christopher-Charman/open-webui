#!/bin/sh
set -eu
umask 077

ACCOUNT="/home/storage/781/4477781/user"
WEBAPP="$ACCOUNT/webapp"
KEEPALIVE="$WEBAPP/bin/secure-mcp-keepalive"
STATE="$WEBAPP/.secure-mcp-keepalive"
SECRET="$STATE/runtime-api-key"
ALIAS="powerpc-local-mcp"
BIN_HINT="$STATE/tunnel-client-bin"

fail() {
  echo "SECURE_MCP_LIFECYCLE_ACCEPTANCE=FAIL"
  echo "reason=$1"
  exit 1
}

[ "$(id -u)" = "2257347" ] || fail "runtime_identity"
[ -x "$KEEPALIVE" ] || fail "keepalive_missing"
[ -s "$BIN_HINT" ] || fail "tunnel_client_hint_missing"
TC="$(cat "$BIN_HINT")"
[ -x "$TC" ] || fail "tunnel_client_missing"
[ -s "$SECRET" ] || fail "runtime_key_file_missing"

mode="$(stat -c '%a' "$SECRET" 2>/dev/null || true)"
[ "$mode" = "600" ] || fail "runtime_key_mode_$mode"

cron="$(crontab -l 2>/dev/null || true)"
reboot_count="$(printf '%s\n' "$cron" | grep -F '# SECURE_MCP_KEEPALIVE_V1' | grep -F '@reboot' | wc -l | tr -d ' ')"
periodic_count="$(printf '%s\n' "$cron" | grep -F '# SECURE_MCP_KEEPALIVE_V1' | grep -v -F '@reboot' | wc -l | tr -d ' ')"
[ "$reboot_count" = "1" ] || fail "cron_reboot_count_$reboot_count"
[ "$periodic_count" = "1" ] || fail "cron_periodic_count_$periodic_count"

"$KEEPALIVE" ensure
"$KEEPALIVE" status >/dev/null

tmp="$STATE/acceptance-status.$$"
"$TC" runtimes status "$ALIAS" --json >"$tmp"
chmod 600 "$tmp"

PY=""
for p in "$WEBAPP/miniconda/bin/python3.12" "$WEBAPP/miniconda/bin/python3" "$WEBAPP/envs/open-terminal/bin/python" /usr/bin/python3; do
  if [ -x "$p" ]; then PY="$p"; break; fi
done
[ -n "$PY" ] || fail "python_missing"

"$PY" - "$tmp" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1]))
def walk(o,key):
    if isinstance(o,dict):
        if key in o: return o[key]
        for v in o.values():
            r=walk(v,key)
            if r is not None: return r
    if isinstance(o,list):
        for v in o:
            r=walk(v,key)
            if r is not None: return r
    return None
running=walk(obj,"process_running")
healthy=walk(obj,"healthy")
ready=walk(obj,"ready")
stale=walk(obj,"stale")
runtime_state=walk(obj,"runtime_state")
if running is not True or healthy is not True or ready is not True or stale is True:
    print("SECURE_MCP_LIFECYCLE_ACCEPTANCE=FAIL")
    print("reason=native_runtime_not_fully_healthy")
    print("process_running="+str(running).lower())
    print("healthy="+str(healthy).lower())
    print("ready="+str(ready).lower())
    print("stale="+str(stale).lower())
    print("runtime_state="+str(runtime_state))
    sys.exit(1)
print("NATIVE_RUNTIME=PASS")
print("process_running=true")
print("healthy=true")
print("ready=true")
print("stale=false")
PY
rm -f "$tmp"

echo "SECURE_MCP_LIFECYCLE_ACCEPTANCE=HOST_PASS"
echo "runtime=fasthost.powerpc"
echo "alias=$ALIAS"
echo "cron_reboot=PASS"
echo "cron_periodic=PASS"
echo "runtime_key_private=PASS"
echo "local_mcp_mode=STDIO_CHILD"
echo "NEXT=DESTROY_ORIGINATING_WEB_TERMINAL_THEN_RECHECK_AFTER_WATCHDOG_INTERVAL_AND_FRESH_ORIGIN_MCP_CALL"
