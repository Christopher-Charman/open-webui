#!/bin/sh
set -eu
umask 077

ACCOUNT="/home/storage/781/4477781/user"
WEBAPP="$ACCOUNT/webapp"
STATE="$WEBAPP/.control-plane-bootstrap"
PPC_INSTALL_COMMIT="94ddb66145f3e8397f7496ce4b74a0433f2855ec"
MCP_KEEPALIVE_INSTALL_COMMIT="9866eead9164993fd55d2b49340be5ffb5086149"
PPC_INSTALL="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PPC_INSTALL_COMMIT/bootstrap-relay/permanent-control/install.sh"
MCP_INSTALL="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$MCP_KEEPALIVE_INSTALL_COMMIT/bootstrap-relay/permanent-control/install-secure-mcp-keepalive.sh"
PPC_SERVICE="$WEBAPP/bin/powerpc-control"
MCP_ACCEPT="$WEBAPP/bin/secure-mcp-keepalive-accept"
RECEIPT="$STATE/host-bootstrap-receipt.txt"
DETAIL="$STATE/host-bootstrap-detail.log"

[ "$(id -u)" = "2257347" ] || { echo "CONTROL_PLANE_BOOTSTRAP=REFUSED unexpected_uid=$(id -u)" >&2; exit 2; }
[ -d "$WEBAPP" ] || { echo "CONTROL_PLANE_BOOTSTRAP=REFUSED webapp_missing" >&2; exit 2; }

mkdir -p "$STATE"
chmod 700 "$STATE"
: >"$RECEIPT"
: >"$DETAIL"
chmod 600 "$RECEIPT" "$DETAIL"

emit() {
  printf '%s\n' "$*" | tee -a "$RECEIPT"
}

fetch_to() {
  url="$1"
  dst="$2"
  curl -fsSL --retry 4 "$url" -o "$dst" || return $?
  chmod 700 "$dst" || return $?
  sh -n "$dst" || return $?
}

run_captured() {
  label="$1"
  shift
  tmp="$STATE/$label.$$.out"
  if "$@" >"$tmp" 2>&1; then
    rc=0
  else
    rc=$?
  fi
  {
    printf '%s\n' "===== $label rc=$rc ====="
    cat "$tmp"
  } >>"$DETAIL"
  rm -f "$tmp"
  return "$rc"
}

emit "CONTROL_PLANE_BOOTSTRAP_BEGIN=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# Phase 1 is deliberately first. Once this receiver is genuinely installed,
# later repair and acceptance work must stop using the Web Terminal as routine
# command transport.
emit "PHASE=OWNED_PRODUCT_INDEPENDENT_RECEIVER"
ppc_script="$STATE/install-permanent-control.$$"
if ! fetch_to "$PPC_INSTALL" "$ppc_script"; then
  emit "OWNED_RECEIVER_HOST=FAIL fetch_or_syntax"
  exit 10
fi
if ! run_captured owned_receiver_install "$ppc_script"; then
  rm -f "$ppc_script"
  emit "OWNED_RECEIVER_HOST=FAIL install"
  exit 11
fi
rm -f "$ppc_script"

# Force the freshly installed daemon/service code into the live process. A
# pre-existing receiver process must not allow source installation to masquerade
# as live acceptance of the new lifecycle or public-receipt implementation.
if ! run_captured owned_receiver_restart "$PPC_SERVICE" restart; then
  emit "OWNED_RECEIVER_HOST=FAIL restart"
  exit 12
fi
sleep 3
if ! run_captured owned_receiver_status "$PPC_SERVICE" status; then
  emit "OWNED_RECEIVER_HOST=FAIL status"
  exit 13
fi

MIRROR="$WEBAPP/envs/openwebui/lib/python3.11/site-packages/open_webui/static/powerpc-control-v1"
if [ ! -s "$MIRROR/identity.json" ] || [ ! -s "$MIRROR/status.json" ]; then
  emit "OWNED_RECEIVER_HOST=FAIL public_mirror_missing"
  exit 14
fi
if ! grep -q '"runtime_id":"fasthost.powerpc"' "$MIRROR/identity.json" || \
   ! grep -q '"state":"ready"' "$MIRROR/status.json"; then
  emit "OWNED_RECEIVER_HOST=FAIL public_mirror_invalid"
  exit 15
fi
emit "OWNED_RECEIVER_STATIC_MIRROR=PASS"

public_tmp="$STATE/public-identity.$"
public_url="https://powerpc-darwin.org/static/powerpc-control-v1/identity.json?t=$(date +%s)"
if curl -fsSL --max-time 15 "$public_url" -o "$public_tmp" 2>>"$DETAIL" && \
   grep -q '"runtime_id":"fasthost.powerpc"' "$public_tmp"; then
  emit "OWNED_RECEIVER_PUBLIC_IDENTITY=PASS"
else
  emit "OWNED_RECEIVER_PUBLIC_IDENTITY=PENDING_EXTERNAL_ACCEPTANCE"
fi
rm -f "$public_tmp"

emit "OWNED_RECEIVER_HOST=PASS"

# Phase 2 hardens the independent OpenAI-family ingress. It reuses the existing
# tunnel and local stdio MCP. Failure here does not roll back the newly installed
# owned receiver, because that receiver is the recovery path for this phase.
emit "PHASE=SECURE_MCP_LIFECYCLE"
mcp_script="$STATE/install-secure-mcp-keepalive.$$"
mcp_rc=0
if ! fetch_to "$MCP_INSTALL" "$mcp_script"; then
  mcp_rc=20
elif ! run_captured secure_mcp_keepalive_install "$mcp_script"; then
  mcp_rc=21
elif ! run_captured secure_mcp_keepalive_accept "$MCP_ACCEPT"; then
  mcp_rc=22
fi
rm -f "$mcp_script"

if [ "$mcp_rc" -eq 0 ]; then
  emit "SECURE_MCP_LIFECYCLE_HOST=PASS"
  emit "CONTROL_PLANE_BOOTSTRAP_HOST=PASS"
else
  emit "SECURE_MCP_LIFECYCLE_HOST=PARTIAL rc=$mcp_rc"
  emit "CONTROL_PLANE_BOOTSTRAP_HOST=PARTIAL"
  emit "RECOVERY_PATH=OWNED_PRODUCT_INDEPENDENT_RECEIVER"
fi

emit "permanent_installer_commit=$PPC_INSTALL_COMMIT"
emit "secure_mcp_installer_commit=$MCP_KEEPALIVE_INSTALL_COMMIT"
emit "FRESH_SESSION_ACCEPTANCE=NOT_YET_PROVEN"
emit "C_AGENT_RECEIVER_ACCEPTANCE=NOT_YET_PROVEN"
emit "NEXT=TERMINATE_THIS_WEB_TERMINAL_SESSION_AND_CONTINUE_ACCEPTANCE_VIA_OWNED_RECEIVER"
emit "CONTROL_PLANE_BOOTSTRAP_END=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

if [ "$mcp_rc" -ne 0 ]; then
  exit "$mcp_rc"
fi
exit 0
