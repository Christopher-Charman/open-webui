#!/bin/sh
set -eu
umask 077

ACCOUNT="/home/storage/781/4477781/user"
WEBAPP="$ACCOUNT/webapp"
STATE="$WEBAPP/.control-plane-bootstrap"
PPC_INSTALL_COMMIT="a1fc69127e85c4ecf2e1d867b531cf5061de238c"
MCP_KEEPALIVE_INSTALL_COMMIT="9866eead9164993fd55d2b49340be5ffb5086149"
PPC_INSTALL="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PPC_INSTALL_COMMIT/bootstrap-relay/permanent-control/install.sh"
MCP_INSTALL="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$MCP_KEEPALIVE_INSTALL_COMMIT/bootstrap-relay/permanent-control/install-secure-mcp-keepalive.sh"
PPC_SERVICE="$WEBAPP/bin/powerpc-control"
MCP_ACCEPT="$WEBAPP/bin/secure-mcp-keepalive-accept"
RECEIPT="$STATE/host-bootstrap-receipt.txt"

[ "$(id -u)" = "2257347" ] || { echo "CONTROL_PLANE_BOOTSTRAP=REFUSED unexpected_uid=$(id -u)" >&2; exit 2; }
[ -d "$WEBAPP" ] || { echo "CONTROL_PLANE_BOOTSTRAP=REFUSED webapp_missing" >&2; exit 2; }

mkdir -p "$STATE"
chmod 700 "$STATE"

fetch_run() {
  name="$1"
  url="$2"
  script="$STATE/$name.$$"
  curl -fsSL --retry 4 "$url" -o "$script"
  chmod 700 "$script"
  sh -n "$script"
  "$script"
  rm -f "$script"
}

{
  echo "CONTROL_PLANE_BOOTSTRAP_BEGIN=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

  # Phase 1 is intentionally first. Once accepted, later repair/acceptance work
  # no longer needs the Web Terminal to act as routine transport.
  echo "PHASE=OWNED_PRODUCT_INDEPENDENT_RECEIVER"
  fetch_run "install-permanent-control.sh" "$PPC_INSTALL"
  "$PPC_SERVICE" status
  echo "OWNED_RECEIVER_HOST=PASS"

  # Phase 2 hardens the independent OpenAI-family ingress. It must reuse the
  # existing tunnel and existing local MCP, never create replacements.
  echo "PHASE=SECURE_MCP_LIFECYCLE"
  if fetch_run "install-secure-mcp-keepalive.sh" "$MCP_INSTALL"; then
    "$MCP_ACCEPT"
    echo "SECURE_MCP_LIFECYCLE_HOST=PASS"
  else
    rc=$?
    echo "SECURE_MCP_LIFECYCLE_HOST=PARTIAL rc=$rc"
    echo "NOTE=owned_receiver_phase_remains_installed_and_must_be_used_for_followup"
  fi

  echo "CONTROL_PLANE_BOOTSTRAP_HOST=PASS"
  echo "permanent_installer_commit=$PPC_INSTALL_COMMIT"
  echo "secure_mcp_installer_commit=$MCP_KEEPALIVE_INSTALL_COMMIT"
  echo "FRESH_SESSION_ACCEPTANCE=NOT_YET_PROVEN"
  echo "C_AGENT_RECEIVER_ACCEPTANCE=NOT_YET_PROVEN"
  echo "NEXT=TERMINATE_THIS_WEB_TERMINAL_SESSION_AND_CONTINUE_ACCEPTANCE_VIA_OWNED_RECEIVER"
  echo "CONTROL_PLANE_BOOTSTRAP_END=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
} | tee "$RECEIPT"

chmod 600 "$RECEIPT"
