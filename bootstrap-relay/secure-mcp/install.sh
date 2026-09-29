#!/usr/bin/env bash
set -euo pipefail
umask 077

ACCOUNT="/home/storage/781/4477781/user"
BASE="$ACCOUNT/webapp"
STATE="$BASE/.secure-mcp-tunnel"
BIN="$BASE/bin/tunnel-client"
LOCAL_MCP="$BASE/bin/local-mcp"
ALIAS="powerpc-local-mcp"
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

PY3="$BASE/miniconda/bin/python3"
[ -x "$PY3" ] || PY3="$(command -v python3 || true)"
[ -n "$PY3" ] || {
  echo "SECURE_MCP=FAIL python3_missing"
  exit 2
}

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
  local api json url sums_url tmp asset sums sha found
  api="https://api.github.com/repos/openai/tunnel-client/releases/latest"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  json="$tmp/release.json"
  curl -fsSL --retry 3 --connect-timeout 10 "$api" -o "$json"

  "$PY3" - "$json" "$tmp/urls" <<'PY'
import json,re,sys
j=json.load(open(sys.argv[1]))
assets=j.get("assets",[])
tag=j.get("tag_name","")
wanted="tunnel-client-%s-linux-amd64.zip" % tag if tag else ""
full=""
sums=""
for a in assets:
    n=a.get("name","")
    if wanted and n == wanted:
        full=a.get("browser_download_url","")
    elif n == "SHA256SUMS.txt":
        sums=a.get("browser_download_url","")
if not full:
    for a in assets:
        n=a.get("name","")
        if re.fullmatch(r"tunnel-client-v[0-9.]+-linux-amd64\.zip", n):
            full=a.get("browser_download_url","")
            break
if not full or not sums:
    raise SystemExit("required official release assets not found")
open(sys.argv[2],"w").write(full+"\n"+sums+"\n")
PY

  url="$(sed -n '1p' "$tmp/urls")"
  sums_url="$(sed -n '2p' "$tmp/urls")"
  asset="$tmp/asset.zip"
  sums="$tmp/SHA256SUMS.txt"

  curl -fsSL --retry 3 --connect-timeout 10 "$url" -o "$asset"
  curl -fsSL --retry 3 --connect-timeout 10 "$sums_url" -o "$sums"

  sha="$(sha256sum "$asset" | awk '{print $1}')"
  grep -qi "^$sha[[:space:]]" "$sums" || {
    echo "SECURE_MCP=FAIL release_checksum_mismatch"
    return 2
  }

  rm -rf "$tmp/unpack"
  mkdir -p "$tmp/unpack"
  "$PY3" - "$asset" "$tmp/unpack" <<'PY'
import sys,zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    z.extractall(sys.argv[2])
PY

  found="$(find "$tmp/unpack" -type f -name tunnel-client | head -1 || true)"
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

"$BIN" --version || true
"$BIN" help quickstart | sed -n '1,80p' || true

TUNNEL_FILE="$STATE/tunnel_id"
KEY_FILE="$STATE/control_plane_api_key"

if [ ! -s "$TUNNEL_FILE" ]; then
  printf 'OpenAI tunnel ID (tunnel_<32 hex>; not secret): ' >/dev/tty
  IFS= read -r tunnel_id </dev/tty
  case "$tunnel_id" in
    tunnel_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f])
      printf '%s\n' "$tunnel_id" >"$TUNNEL_FILE"
      chmod 600 "$TUNNEL_FILE"
      ;;
    *)
      echo "SECURE_MCP=CLIENT_READY"
      echo "NEXT_HUMAN_BOUNDARY=create_or_select_tunnel_id"
      echo "Open: https://platform.openai.com/settings/organization/tunnels"
      exit 0
      ;;
  esac
fi

if [ ! -s "$KEY_FILE" ]; then
  printf 'Runtime API key with Tunnels Read+Use (input hidden): ' >/dev/tty
  IFS= read -r -s key </dev/tty
  printf '\n' >/dev/tty
  [ -n "$key" ] || {
    echo "SECURE_MCP=CLIENT_READY"
    echo "NEXT_HUMAN_BOUNDARY=runtime_api_key_missing"
    echo "Open: https://platform.openai.com/settings/organization/api-keys"
    exit 0
  }
  printf '%s\n' "$key" >"$KEY_FILE"
  chmod 600 "$KEY_FILE"
  unset key
fi

TUNNEL_ID="$(cat "$TUNNEL_FILE")"
export CONTROL_PLANE_API_KEY="$(cat "$KEY_FILE")"

echo "== configure local stdio MCP profile =="
"$BIN" init   --sample sample_mcp_stdio_local   --profile "$PROFILE"   --tunnel-id "$TUNNEL_ID"   --mcp-command "$LOCAL_MCP"   --force

echo "== doctor =="
"$BIN" doctor --profile "$PROFILE" --explain

echo "== managed runtime =="
"$BIN" runtimes stop "$ALIAS" >/dev/null 2>&1 || true
"$BIN" runtimes rm "$ALIAS" >/dev/null 2>&1 || true

"$BIN" runtimes connect   --alias "$ALIAS"   --tunnel-id "$TUNNEL_ID"   --runtime-api-key env:CONTROL_PLANE_API_KEY   --mcp-command "$LOCAL_MCP"

echo "== status =="
"$BIN" runtimes --json status "$ALIAS"

echo "SECURE_MCP=CONNECTED"
echo "alias=$ALIAS"
echo "tunnel_id=$TUNNEL_ID"
echo "local_mcp=$LOCAL_MCP"
