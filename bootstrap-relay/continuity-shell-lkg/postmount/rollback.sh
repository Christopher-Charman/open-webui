#!/usr/bin/env bash
set -Eeuo pipefail

BASE="${HOME}/webapp"
PKG="${BASE}/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="${PKG}/frontend"
STATIC_A="${PKG}/static"
STATIC_B="${FRONTEND}/static"

BACKUP="${1:-}"
[ -n "$BACKUP" ] || { echo "usage: $0 /absolute/path/to/pre-semantic-binder-BACKUP"; exit 2; }
[ -f "$BACKUP/index.html" ] || { echo "ERROR invalid backup: $BACKUP"; exit 3; }

cp -a "$BACKUP/index.html" "$FRONTEND/index.html"
for name in continuity-shell-semantic-binder.js continuity-shell-semantic-binder.css; do
  if [ -f "$BACKUP/$name" ]; then
    cp -a "$BACKUP/$name" "$STATIC_A/$name"
    cp -a "$BACKUP/$name" "$STATIC_B/$name"
  else
    rm -f "$STATIC_A/$name" "$STATIC_B/$name"
  fi
done

echo "SEMANTIC_BINDER_ROLLBACK=PASS"
echo "restart=NOT_PERFORMED"
