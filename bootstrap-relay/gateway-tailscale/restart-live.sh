#!/usr/bin/env bash
set -euo pipefail

TS="$HOME/tailscale"
BIN="$TS/bin"
STATE="$TS/state"
SOCK="$STATE/tailscaled.sock"
PIDFILE="$STATE/tailscaled.pid"
LOG="$STATE/tailscaled.log"
EXPECTED_IP="100.118.16.80"

test -x "$BIN/tailscaled"
test -x "$BIN/tailscale"
test -s "$STATE/tailscaled.state"
command -v setsid >/dev/null 2>&1

live=0
if [ -s "$PIDFILE" ]; then
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    if tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -Fq "$BIN/tailscaled"; then
      live=1
    fi
  fi
fi

if [ "$live" -eq 0 ]; then
  rm -f "$SOCK" "$PIDFILE"
  printf '\n[%s] gateway-tailscale bounded restart\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$LOG"
  setsid "$BIN/tailscaled" \
    --tun=userspace-networking \
    --state="$STATE/tailscaled.state" \
    --socket="$SOCK" \
    >>"$LOG" 2>&1 </dev/null &
  pid="$!"
  printf '%s\n' "$pid" >"$PIDFILE"
  echo "TAILSCALED_RESTARTED=$pid"
else
  echo "TAILSCALED_ALREADY_LIVE=$pid"
fi

for _ in $(seq 1 80); do
  if [ -S "$SOCK" ] && kill -0 "$pid" 2>/dev/null; then
    break
  fi
  sleep 0.25
done

[ -S "$SOCK" ]
kill -0 "$pid" 2>/dev/null

echo "TAILSCALE_STATUS_BEGIN"
"$BIN/tailscale" --socket="$SOCK" status --peers=false
echo "TAILSCALE_STATUS_END"

ip4="$("$BIN/tailscale" --socket="$SOCK" ip -4 | head -n 1)"
echo "TAILSCALE_IPV4=$ip4"
[ "$ip4" = "$EXPECTED_IP" ]

echo "TAILSCALE_SERVE_BEGIN"
"$BIN/tailscale" --socket="$SOCK" serve status
echo "TAILSCALE_SERVE_END"

python3 - <<'PY'
import socket
checks=[
    ("127.0.0.1",2222,"MGMT_SSHD_LOCAL"),
    ("100.118.16.80",22,"TAILSCALE_SELF_22"),
]
for host,port,label in checks:
    s=socket.socket()
    s.settimeout(5)
    try:
        s.connect((host,port))
        try:
            data=s.recv(128)
        except Exception:
            data=b""
        banner=data.decode("ascii","replace").strip()[:96]
        print(f"{label}=TCP_PASS BANNER={banner}")
    except Exception as e:
        print(f"{label}=TCP_FAIL ERROR={type(e).__name__}:{e}")
        raise SystemExit(1)
    finally:
        s.close()
PY

echo "GATEWAY_TAILSCALE_HOST_RESTORE=PASS"
echo "MUTATION=TAILSCALED_RESTART_ONLY"
