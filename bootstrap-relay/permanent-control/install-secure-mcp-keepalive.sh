#!/bin/sh
set -eu
umask 077

ACCOUNT="${PPC_ACCOUNT:-${HOME}}"
WEBAPP="$ACCOUNT/webapp"
STATE="$WEBAPP/.secure-mcp-keepalive"
TARGET="$WEBAPP/bin/secure-mcp-keepalive"
ACCEPT="$WEBAPP/bin/secure-mcp-keepalive-accept"
PROFILE_DIR="$WEBAPP/.config/tunnel-client"
ALIAS="powerpc-local-mcp"
SECRET_FILE="$STATE/runtime-api-key"
BIN_HINT="$STATE/tunnel-client-bin"
PIN="5568fb491606b354498ef7877da1b005c783ed7c"
BASE="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/permanent-control"

[ "$(id -u)" = "2257347" ] || { echo "REFUSED unexpected uid=$(id -u)" >&2; exit 2; }
[ -d "$WEBAPP" ] || { echo "REFUSED webapp missing" >&2; exit 2; }
[ -x "$WEBAPP/bin/local-mcp" ] || { echo "REFUSED local MCP missing" >&2; exit 2; }
[ -d "$PROFILE_DIR" ] || { echo "REFUSED tunnel-client profile dir missing" >&2; exit 2; }

mkdir -p "$STATE" "$WEBAPP/bin"
chmod 700 "$STATE"
was_disabled=0
[ ! -e "$STATE/disabled" ] || was_disabled=1

resolve_bin() {
  if [ -n "${TUNNEL_CLIENT_BIN:-}" ] && [ -x "$TUNNEL_CLIENT_BIN" ]; then
    printf '%s\n' "$TUNNEL_CLIENT_BIN"
    return 0
  fi
  for b in "$WEBAPP/bin/tunnel-client" "$WEBAPP/.local/bin/tunnel-client" "$ACCOUNT/.local/bin/tunnel-client"; do
    if [ -x "$b" ]; then printf '%s\n' "$b"; return 0; fi
  done
  command -v tunnel-client 2>/dev/null || return 1
}

TC="$(resolve_bin)" || { echo "REFUSED tunnel-client missing" >&2; exit 2; }
printf '%s\n' "$TC" >"$BIN_HINT"
chmod 600 "$BIN_HINT"

# The accepted runtime profile references env:CONTROL_PLANE_API_KEY. Cron does
# not inherit an interactive Web Terminal environment, so migrate the already
# present host-side value into a private file reference without printing it.
if [ ! -s "$SECRET_FILE" ] || [ "${SECURE_MCP_REFRESH_RUNTIME_KEY:-0}" = "1" ]; then
  if [ -n "${CONTROL_PLANE_API_KEY:-}" ]; then
    tmp="$STATE/runtime-api-key.$$"
    printf '%s' "$CONTROL_PLANE_API_KEY" >"$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$SECRET_FILE"
    echo "RUNTIME_KEY_MIGRATION=CAPTURED_FROM_EXISTING_HOST_ENV"
  elif [ ! -s "$SECRET_FILE" ]; then
    echo "RUNTIME_KEY_MIGRATION=REQUIRED" >&2
    echo "REFUSED no private runtime-key file exists and CONTROL_PLANE_API_KEY is absent from this host process" >&2
    exit 3
  fi
fi
chmod 600 "$SECRET_FILE"

tmp="$STATE/secure-mcp-keepalive.$$"
curl -fsSL --retry 4 "$BASE/secure-mcp-keepalive" -o "$tmp"
chmod 700 "$tmp"
sh -n "$tmp"
mv -f "$tmp" "$TARGET"
chmod 700 "$TARGET"

tmp="$STATE/accept-secure-mcp-keepalive.$$"
curl -fsSL --retry 4 "$BASE/accept-secure-mcp-keepalive.sh" -o "$tmp"
chmod 700 "$tmp"
sh -n "$tmp"
mv -f "$tmp" "$ACCEPT"
chmod 700 "$ACCEPT"

MARK="# SECURE_MCP_KEEPALIVE_V1"
TMP="$STATE/crontab.$$"
(crontab -l 2>/dev/null || true) | awk -v m="$MARK" '$0 !~ m {print}' >"$TMP"
printf '%s\n' \
  "@reboot $TARGET ensure >/dev/null 2>&1 $MARK" \
  "* * * * * $TARGET ensure >/dev/null 2>&1 $MARK" >>"$TMP"
crontab "$TMP"
rm -f "$TMP"

if [ "$was_disabled" = "1" ]; then
  echo "DESIRED_STATE=DISABLED_PRESERVED"
  "$TARGET" status
else
  "$TARGET" enable
  "$TARGET" status
fi

echo "SECURE_MCP_KEEPALIVE_INSTALL=PASS"
echo "alias=$ALIAS"
echo "supervision=NATIVE_TUNNEL_RUNTIME_PLUS_CRON_HEALTH_ENSURE"
echo "local_mcp=STDIO_CHILD_NOT_DAEMONIZED"
echo "runtime_key=file:$SECRET_FILE"
echo "acceptance=$ACCEPT"
echo "source_commit=$PIN"
