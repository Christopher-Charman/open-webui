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
ORG_ID="org-8kCZgBLHOGW9Efv95xjeoXya"
EXAMPLE_TUNNEL_ID="tunnel_0123456789abcdef0123456789abcdef"

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

TUNNEL_FILE="$STATE/tunnel_id"
KEY_FILE="$STATE/control_plane_api_key"
META_FILE="$STATE/tunnel-meta.json"
STATUS_FILE="$STATE/runtime-status.json"

if [ "${RESET_RUNTIME_KEY:-0}" = "1" ]; then
  rm -f "$KEY_FILE"
  echo "runtime_key_reset=YES"
fi

# Remove the documentation example if it was accidentally entered as though real.
if [ -s "$TUNNEL_FILE" ] && [ "$(cat "$TUNNEL_FILE")" = "$EXAMPLE_TUNNEL_ID" ]; then
  echo "example_tunnel_id_detected=YES"
  rm -f "$TUNNEL_FILE"
fi

create_tunnel_with_admin_key() {
  local admin out tid
  printf 'Admin API key for one-time tunnel creation (input hidden): ' >/dev/tty
  IFS= read -r -s admin </dev/tty
  printf '\n' >/dev/tty
  [ -n "$admin" ] || return 1

  export OPENAI_ADMIN_KEY="$admin"
  unset admin

  out="$STATE/tunnel-create.json"
  if ! "$BIN" admin --json tunnels create       --name "PowerPC Local MCP"       --description "Private tunnel to the PowerPC local stdio MCP"       --organization-id "$ORG_ID" >"$out"; then
    unset OPENAI_ADMIN_KEY
    echo "SECURE_MCP=FAIL tunnel_create_failed"
    cat "$out" 2>/dev/null || true
    return 2
  fi
  unset OPENAI_ADMIN_KEY

  tid="$("$PY3" - "$out" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))
print(j.get("id",""))
PY
)"
  case "$tid" in
    tunnel_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f])
      printf '%s\n' "$tid" >"$TUNNEL_FILE"
      chmod 600 "$TUNNEL_FILE"
      echo "tunnel_created=$tid"
      echo "waiting_for_tunnel_activation=30s"
      sleep 30
      ;;
    *)
      echo "SECURE_MCP=FAIL tunnel_create_returned_no_valid_id"
      return 2
      ;;
  esac
}

if [ ! -s "$TUNNEL_FILE" ]; then
  printf 'OpenAI tunnel ID (leave blank to create one here with an Admin API key): ' >/dev/tty
  IFS= read -r tunnel_id </dev/tty

  if [ -n "$tunnel_id" ]; then
    [ "$tunnel_id" != "$EXAMPLE_TUNNEL_ID" ] || {
      echo "SECURE_MCP=FAIL documentation_example_is_not_a_real_tunnel"
      rm -f "$TUNNEL_FILE"
      exit 2
    }
    if ! "$PY3" - "$tunnel_id" <<'PY'
import re,sys
raise SystemExit(0 if re.fullmatch(r"tunnel_[0-9a-f]{32}",sys.argv[1]) else 1)
PY
    then
      echo "SECURE_MCP=FAIL invalid_tunnel_id_format"
      exit 2
    fi
    printf '%s\n' "$tunnel_id" >"$TUNNEL_FILE"
    chmod 600 "$TUNNEL_FILE"
  else
    if ! create_tunnel_with_admin_key; then
      echo "SECURE_MCP=CLIENT_READY"
      echo "NEXT_HUMAN_BOUNDARY=create_tunnel"
      echo "Open: https://platform.openai.com/settings/organization/tunnels"
      exit 0
    fi
  fi
fi

TUNNEL_ID="$(cat "$TUNNEL_FILE")"

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

export CONTROL_PLANE_API_KEY="$(cat "$KEY_FILE")"

echo "== verify remote tunnel with runtime key =="
if ! "$BIN" admin --json tunnels get "$TUNNEL_ID" >"$META_FILE"; then
  echo "SECURE_MCP=FAIL tunnel_lookup_failed"
  cat "$META_FILE" 2>/dev/null || true
  rm -f "$TUNNEL_FILE"
  echo "NEXT=rerun installer with a real tunnel ID, or leave the ID blank to create one with an Admin API key"
  exit 2
fi

if ! "$PY3" - "$META_FILE" "$TUNNEL_ID" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))
if j.get("id") != sys.argv[2]:
    raise SystemExit(1)
PY
then
  echo "SECURE_MCP=FAIL tunnel_metadata_mismatch"
  exit 2
fi

echo "== configure local stdio MCP profile =="
"$BIN" init   --sample sample_mcp_stdio_local   --profile "$PROFILE"   --tunnel-id "$TUNNEL_ID"   --mcp-command "$LOCAL_MCP"   --force

echo "== doctor =="
"$BIN" doctor --profile "$PROFILE" --explain

echo "== managed runtime =="
"$BIN" runtimes stop "$ALIAS" >/dev/null 2>&1 || true
"$BIN" runtimes rm "$ALIAS" >/dev/null 2>&1 || true

"$BIN" runtimes connect   --alias "$ALIAS"   --tunnel-id "$TUNNEL_ID"   --runtime-api-key env:CONTROL_PLANE_API_KEY   --mcp-command "$LOCAL_MCP"

echo "== status =="
"$BIN" runtimes --json status "$ALIAS" >"$STATUS_FILE"
cat "$STATUS_FILE"

if ! "$PY3" - "$STATUS_FILE" "$TUNNEL_ID" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))
checks = [
    j.get("tunnel_id") == sys.argv[2],
    j.get("process_running") is True,
    j.get("healthy") is True,
    j.get("ready") is True,
    not j.get("remote_error"),
    j.get("remote") is not None,
]
raise SystemExit(0 if all(checks) else 1)
PY
then
  echo "SECURE_MCP=FAIL acceptance_gate"
  echo "The local alias exists, but the OpenAI tunnel is not fully live/authorized."
  exit 2
fi

echo "SECURE_MCP=CONNECTED_VERIFIED"
echo "alias=$ALIAS"
echo "tunnel_id=$TUNNEL_ID"
echo "local_mcp=$LOCAL_MCP"
