#!/usr/bin/env bash
set -eu

BASE="/home/storage/781/4477781/user/webapp"
PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"

echo "SEMANTIC_WRITER_SUMMARY=BEGIN"
echo "mode=READ_ONLY"

for marker in   custom-shell-landing   custom-shell-prompt   custom-shell-sidebar   custom-shell-footer   hero-network   hero-aura   orb-slot   chat-telemetry   "COMPUTER CORE"   "WORLD BETWEEN WORLDS"
do
  echo
  echo "MARKER=$marker"
  find "$PKG" -maxdepth 6 -type f \( -name '*.js' -o -name '*.html' \)     -path '*/frontend*/*'     ! -name loader.js     ! -name pwa-voice-bridge.js     ! -name pwa-client-runtime.js     -print0 2>/dev/null |
  while IFS= read -r -d '' f; do
    if grep -Fq "$marker" "$f" 2>/dev/null; then
      h="$(sha256sum "$f" | awk '{print $1}')"
      echo "  FILE=$f"
      echo "  SHA256=$h"
      python3 - "$f" "$marker" <<'PY'
from pathlib import Path
import sys,re
p=Path(sys.argv[1]); marker=sys.argv[2]
s=p.read_text(errors="ignore")
i=s.find(marker)
if i>=0:
    c=s[max(0,i-350):min(len(s),i+700)]
    print("  CONTEXT="+re.sub(r"\s+"," ",c)[:1000])
PY
    fi
  done
done

echo
echo "BOUNDARY=NO_RUNTIME_MUTATION"
echo "loader_restore=FORBIDDEN"
echo "voice_bridge_restore=FORBIDDEN"
echo "client_runtime_restore=FORBIDDEN"
echo "SEMANTIC_WRITER_SUMMARY=END"
