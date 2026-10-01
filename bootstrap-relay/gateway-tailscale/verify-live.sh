#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/storage/781/4477781/user/webapp"
TS="$ROOT/tailscale"
BIN="$TS/bin"
STATE="$TS/state"
SOCK="$STATE/tailscaled.sock"
PIDFILE="$STATE/tailscaled.pid"
EXPECTED_IP="100.118.16.80"

test -x "$BIN/tailscale"
test -x "$BIN/tailscaled"
test -S "$SOCK"
test -s "$PIDFILE"

pid="$(cat "$PIDFILE")"
[[ "$pid" =~ ^[0-9]+$ ]]
kill -0 "$pid" 2>/dev/null
proc_exe="$(readlink -f "/proc/$pid/exe")"
expected_exe="$(readlink -f "$BIN/tailscaled")"
[ "$proc_exe" = "$expected_exe" ]

echo "TAILSCALED_PID=$pid"
echo "TAILSCALED_EXE=$proc_exe"

echo "TAILSCALE_STATUS_BEGIN"
"$BIN/tailscale" --socket="$SOCK" status --peers=false
echo "TAILSCALE_STATUS_END"

ip4="$("$BIN/tailscale" --socket="$SOCK" ip -4 | head -n 1)"
echo "TAILSCALE_IPV4=$ip4"
[ "$ip4" = "$EXPECTED_IP" ]

serve="$("$BIN/tailscale" --socket="$SOCK" serve status)"
echo "TAILSCALE_SERVE_BEGIN"
printf '%s\n' "$serve"
echo "TAILSCALE_SERVE_END"

printf '%s\n' "$serve" | grep -F "tcp://100.118.16.80:22" >/dev/null
printf '%s\n' "$serve" | grep -F "tcp://127.0.0.1:2222" >/dev/null

python3 - <<'PY'
import socket
s=socket.socket()
s.settimeout(5)
try:
    s.connect(("127.0.0.1",2222))
    data=s.recv(128)
    banner=data.decode("ascii","replace").strip()
    print("MGMT_SSHD_LOCAL=TCP_PASS")
    print("MGMT_SSHD_BANNER="+banner[:96])
    assert banner.startswith("SSH-2.0-OpenSSH_7.4"), banner
finally:
    s.close()
PY

echo "GATEWAY_TAILSCALE_HOST_ACCEPTANCE=PASS"
echo "MUTATION=NONE"
