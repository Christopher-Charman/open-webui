#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
RESTART="$BASE/restart-openwebui-via-passenger.sh"
LAUNCHER="$BASE/run-openwebui.sh"
PIN="8f91c9772abf193b31d90373e80c5f4c05bafa0f"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/stock-bootstrap-isolation/restore.py"
CACHE_GEN="stock-bootstrap-20260929.1"

TMP="$(mktemp)"
OUT="$(mktemp)"
PUBLIC_HTML="$(mktemp)"
PUBLIC_LOADER="$(mktemp)"
PUBLIC_CSS="$(mktemp)"
trap 'rm -f "$TMP" "$OUT" "$PUBLIC_HTML" "$PUBLIC_LOADER" "$PUBLIC_CSS"' EXIT

curl -fsSL --retry 3 --connect-timeout 10 "$RAW" -o "$TMP"
python3 "$TMP" | tee "$OUT"

grep -Fq 'STOCK_BOOTSTRAP=STAGED_ON_DISK_PASS' "$OUT" || {
  echo "STOCK_BOOTSTRAP=FAIL staging_receipt_missing"
  exit 2
}

grep -Fq 'export WEBUI_AUTH=True' "$LAUNCHER" || {
  echo "STOCK_BOOTSTRAP=FAIL native_openwebui_auth_not_enabled"
  exit 2
}

test -x "$RESTART" || {
  echo "STOCK_BOOTSTRAP=FAIL restart_script_missing"
  exit 2
}

"$RESTART"

local_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18080/health || true)"
[ "$local_code" = "200" ] || {
  echo "STOCK_BOOTSTRAP=FAIL local_health_http=$local_code"
  exit 2
}

probe="https://powerpc-darwin.org/?__stock_bootstrap=$(date +%s)"
curl -fsSL --retry 3 --connect-timeout 10 --max-time 25 \
  -H 'Cache-Control: no-cache' \
  -H 'Pragma: no-cache' \
  "$probe" -o "$PUBLIC_HTML" || {
    echo "STOCK_BOOTSTRAP=FAIL public_html_fetch"
    exit 2
  }

grep -Fq 'owui-stock-bootstrap-isolation-v20260929.1' "$PUBLIC_HTML" || {
  echo "STOCK_BOOTSTRAP=FAIL public_marker_missing"
  exit 2
}
grep -Fq "/static/loader.js?v=$CACHE_GEN" "$PUBLIC_HTML" || {
  echo "STOCK_BOOTSTRAP=FAIL public_loader_generation_missing"
  exit 2
}
grep -Fq "/static/custom.css?v=$CACHE_GEN" "$PUBLIC_HTML" || {
  echo "STOCK_BOOTSTRAP=FAIL public_css_generation_missing"
  exit 2
}

# Known custom bootstrap modules must not be advertised by the live document.
for name in \
  pwa-client-runtime.js \
  pwa-voice-bridge.js \
  lcars-runtime.js \
  lcars-theme.css \
  continuity-shell-registry.js \
  continuity-controls.js \
  continuity-settings.js \
  owui-orb-v1.js \
  owui-orb-v1.css \
  owui-border-beam-v1.js \
  owui-border-beam-v1.css
do
  if grep -Fq "/static/$name" "$PUBLIC_HTML"; then
    echo "STOCK_BOOTSTRAP=FAIL custom_bootstrap_ref_present=$name"
    exit 2
  fi
done

curl -fsSL --retry 3 --max-time 20 \
  "https://powerpc-darwin.org/static/loader.js?v=$CACHE_GEN&cb=$(date +%s)" -o "$PUBLIC_LOADER"
curl -fsSL --retry 3 --max-time 20 \
  "https://powerpc-darwin.org/static/custom.css?v=$CACHE_GEN&cb=$(date +%s)" -o "$PUBLIC_CSS"

loader_bytes="$(wc -c < "$PUBLIC_LOADER" | tr -d ' ')"
css_bytes="$(wc -c < "$PUBLIC_CSS" | tr -d ' ')"

[ "$loader_bytes" = "0" ] || {
  echo "STOCK_BOOTSTRAP=FAIL public_loader_bytes=$loader_bytes"
  exit 2
}
[ "$css_bytes" = "0" ] || {
  echo "STOCK_BOOTSTRAP=FAIL public_custom_css_bytes=$css_bytes"
  exit 2
}

app="$(python3 - "$PUBLIC_HTML" <<'PY'
import re, sys
s=open(sys.argv[1]).read()
m=re.search(r'/_app/immutable/entry/(app\.[^"\']+\.js)', s)
print(m.group(0) if m else '')
PY
)"
[ -n "$app" ] || {
  echo "STOCK_BOOTSTRAP=FAIL public_app_entry_missing"
  exit 2
}
app_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://powerpc-darwin.org$app?cb=$(date +%s)" || true)"
[ "$app_code" = "200" ] || {
  echo "STOCK_BOOTSTRAP=FAIL public_stock_app_http=$app_code"
  exit 2
}

echo "STOCK_BOOTSTRAP=PUBLIC_PASS"
echo "ownership=OPENWEBUI_BOOTSTRAP_ONLY"
echo "native_openwebui_auth=PASS"
echo "custom_assets_deleted=NO"
echo "backend_services_changed=NO"
echo "local_health_http=$local_code"
echo "public_loader_bytes=$loader_bytes"
echo "public_custom_css_bytes=$css_bytes"
echo "stock_app=$app"
echo "stock_app_http=$app_code"
echo "NEXT=FORCE_CLOSE_REOPEN_SAFARI_THEN_HOME_SCREEN_PWA"
