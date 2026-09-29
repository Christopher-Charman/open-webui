#!/usr/bin/env bash
set -euo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
STATE="$BASE/.tavily-bootstrap"
PY="$BASE/miniconda/bin/python3"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/4301b89a8bf65b8c70bf09cd2ac20b0c82be28f5/bootstrap-relay/tavily-bootstrap-bridge.py"

mkdir -p "$STATE"
chmod 700 "$STATE"

curl -fsSL "$RAW" -o "$STATE/bridge.py"
chmod 600 "$STATE/bridge.py"

OLD="$(pgrep -f "$STATE/[b]ridge.py" || true)"
if [ -n "$OLD" ]; then
  kill $OLD 2>/dev/null || true
  sleep 1
fi

nohup "$PY" "$STATE/bridge.py" >"$STATE/bridge.log" 2>&1 </dev/null &
echo $! >"$STATE/bridge.pid"

code=""
for _ in $(seq 1 40); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 http://127.0.0.1:18765/O4k2rOOgzzYHQxi4HKKKPTrqouXFUwme/status || true)"
  [ "$code" = "200" ] && break
  sleep 0.25
done

[ "${code:-}" = "200" ] || {
  echo "BRIDGE_LOCAL=FAIL"
  tail -40 "$STATE/bridge.log" || true
  exit 1
}

if [ -f "$STATE/tunnel.pid" ]; then
  TPID="$(cat "$STATE/tunnel.pid" 2>/dev/null || true)"
  [ -n "$TPID" ] && kill "$TPID" 2>/dev/null || true
fi
rm -f "$STATE/tunnel.jsonl" "$STATE/tunnel.url"

nohup ssh -T   -o BatchMode=yes   -o ConnectTimeout=10   -o ServerAliveInterval=30   -o ServerAliveCountMax=3   -o ExitOnForwardFailure=yes   -o StrictHostKeyChecking=no   -o UserKnownHostsFile="$STATE/known_hosts"   -R "80:127.0.0.1:18765"   nokey@localhost.run -- --output json   >"$STATE/tunnel.jsonl" 2>&1 </dev/null &

echo $! >"$STATE/tunnel.pid"

URL=""
for _ in $(seq 1 60); do
  URL="$("$PY" - "$STATE/tunnel.jsonl" <<'PY'
import json,sys,re
p=sys.argv[1]
try:
    lines=open(p,"r",errors="replace")
except OSError:
    raise SystemExit
for line in lines:
    try:
        j=json.loads(line)
    except Exception:
        m=re.search(r'https://[A-Za-z0-9.-]+',line)
        if m and m.group(0)!="https://localhost.run":
            print(m.group(0)); break
        continue
    if j.get("event")=="tcpip-forward":
        a=(j.get("address") or j.get("listen_host") or "").strip()
        if a and a!="localhost.run":
            print(a if a.startswith("http") else "https://"+a)
            break
PY
)"
  [ -n "$URL" ] && break
  TPID="$(cat "$STATE/tunnel.pid")"
  kill -0 "$TPID" 2>/dev/null || break
  sleep 0.5
done

[ -n "$URL" ] || {
  echo "TUNNEL=FAIL"
  tail -40 "$STATE/tunnel.jsonl" || true
  exit 1
}

printf '%s\n' "$URL" >"$STATE/tunnel.url"
echo "TAVILY_BRIDGE=READY"
echo "control=$URL"
echo "Send ChatGPT only the control URL."
