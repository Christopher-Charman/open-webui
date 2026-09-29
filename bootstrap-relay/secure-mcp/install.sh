#!/usr/bin/env bash
set -euo pipefail
umask 077

ACCOUNT="/home/storage/781/4477781/user"
BASE="$ACCOUNT/webapp"
STATE="$BASE/.secure-mcp-tunnel"
BIN="$BASE/bin/tunnel-client"
LOCAL_MCP="$BASE/bin/local-mcp"
PROFILE="powerpc-local-mcp"

[ "$(id -u)" = "2257347" ] || {
  echo "SECURE_MCP=REFUSED uid=$(id -u) expected=2257347"
  exit 2
}
[ -x "$LOCAL_MCP" ] || {
  echo "SECURE_MCP=FAIL missing_local_mcp=$LOCAL_MCP"
  exit 2
}

mkdir -p "$STATE" "$BASE/bin"
chmod 700 "$STATE"

echo "== PowerPC identity =="
id
printf 'account=%s\nwebapp=%s\n' "$ACCOUNT" "$BASE"

echo "== local MCP regression smoke =="
NODE="$BASE/.local/node22-glibc217/bin/node"
SMOKE="$BASE/runtime-domains/local-mcp/client-smoke.mjs"
if [ -x "$NODE" ] && [ -f "$SMOKE" ]; then
  "$NODE" "$SMOKE"
else
  echo "local_mcp_smoke=SKIP client_smoke_missing"
fi

install_client() {
  local api json url sums_url tmp asset sums sha
  api="https://api.github.com/repos/openai/tunnel-client/releases/latest"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  json="$tmp/release.json"
  curl -fsSL --retry 3 --connect-timeout 10 "$api" -o "$json"

  python3 - "$json" "$tmp/urls" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))
assets=j.get("assets",[])
def pick(pred):
    for a in assets:
        n=a.get("name","")
        if pred(n):
            return a.get("browser_download_url","")
    return ""
full=pick(lambda n: n=="linux-amd64.zip")
if not full:
    full=pick(lambda n: "linux-amd64" in n and n.endswith(".zip") and "runtime" not in n)
sums=pick(lambda n: n=="SHA256SUMS.txt")
if not full or not sums:
    raise SystemExit("required release assets not found")
open(sys.argv[2],"w").write(full+"\n"+sums+"\n")
PY

  url="$(sed -n '1p' "$tmp/urls")"
  sums_url="$(sed -n '2p' "$tmp/urls")"
  asset="$tmp/asset.zip"
  sums="$tmp/SHA256SUMS.txt"

  curl -fsSL --retry 3 --connect-timeout 10 "$url" -o "$asset"
  curl -fsSL --retry 3 --connect-timeout 10 "$sums_url" -o "$sums"

  sha="$(sha256sum "$asset" | awk '{print $1}')"
  if ! grep -qi "^$sha[[:space:]]" "$sums"; then
    echo "SECURE_MCP=FAIL release_checksum_mismatch"
    return 2
  fi

  rm -rf "$tmp/unpack"
  mkdir -p "$tmp/unpack"
  unzip -q "$asset" -d "$tmp/unpack"
  found="$(find "$tmp/unpack" -type f -name tunnel-client -perm -u+x | head -1 || true)"
  if [ -z "$found" ]; then
    found="$(find "$tmp/unpack" -type f -name tunnel-client | head -1 || true)"
  fi
  [ -n "$found" ] || {
    echo "SECURE_MCP=FAIL tunnel_client_binary_missing"
    return 2
  }

  install -m 700 "$found" "$BIN"
}

if [ ! -x "$BIN" ]; then
  echo "== installing official OpenAI tunnel-client =="
  install_client
else
  echo "tunnel_client=present"
fi

"$BIN" version 2>/dev/null || "$BIN" --version 2>/dev/null || true

TUNNEL_FILE="$STATE/tunnel_id"
KEY_FILE="$STATE/control_plane_api_key"

if [ ! -s "$TUNNEL_FILE" ]; then
  echo
  echo "SECURE_MCP=CLIENT_READY"
  echo "NEXT_HUMAN_BOUNDARY=tunnel_id_missing"
  echo "Create/select the OpenAI MCP tunnel, then rerun this installer."
  echo "The installer will prompt locally and will not echo the runtime key."
  exit 0
fi

if [ ! -s "$KEY_FILE" ]; then
  printf 'Runtime API key (input hidden): ' >/dev/tty
  IFS= read -r -s key </dev/tty
  printf '\n' >/dev/tty
  [ -n "$key" ] || { echo "SECURE_MCP=FAIL empty_runtime_key"; exit 2; }
  printf '%s\n' "$key" >"$KEY_FILE"
  chmod 600 "$KEY_FILE"
  unset key
fi

TUNNEL_ID="$(cat "$TUNNEL_FILE")"
export CONTROL_PLANE_API_KEY="$(cat "$KEY_FILE")"

"$BIN" init   --sample sample_mcp_stdio_local   --profile "$PROFILE"   --tunnel-id "$TUNNEL_ID"   --mcp-command "$LOCAL_MCP"   --force

"$BIN" doctor --profile "$PROFILE" --explain

PIDFILE="$STATE/tunnel-client.pid"
LOG="$STATE/tunnel-client.log"
if [ -s "$PIDFILE" ]; then
  old="$(cat "$PIDFILE" 2>/dev/null || true)"
  [ -n "$old" ] && kill "$old" 2>/dev/null || true
  sleep 1
fi

nohup env CONTROL_PLANE_API_KEY="$CONTROL_PLANE_API_KEY"   "$BIN" run --profile "$PROFILE"   >"$LOG" 2>&1 </dev/null &
pid=$!
printf '%s\n' "$pid" >"$PIDFILE"

sleep 2
if kill -0 "$pid" 2>/dev/null; then
  echo "SECURE_MCP=RUNNING"
  echo "pid=$pid"
  echo "profile=$PROFILE"
  echo "tunnel_id=$TUNNEL_ID"
  echo "local_mcp=$LOCAL_MCP"
else
  echo "SECURE_MCP=FAIL daemon_exited"
  tail -60 "$LOG" || true
  exit 2
fi
