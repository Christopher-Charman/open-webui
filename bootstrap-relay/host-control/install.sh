#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$HERE/secure-mcp/install.sh"

if [ ! -f "$TARGET" ]; then
  echo "HOST_CONTROL_INSTALLER=SUPERSEDED"
  echo "reason=secure_mcp_installer_missing"
  exit 2
fi

echo "HOST_CONTROL_INSTALLER=SUPERSEDED_BY_SECURE_MCP"
exec /bin/bash "$TARGET"
