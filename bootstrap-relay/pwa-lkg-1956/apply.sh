#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
RESTART="$BASE/restart-openwebui-via-passenger.sh"
PIN="7219c68ae073848457046042681b38efb57dc996"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/pwa-lkg-1956/restore.py"
CACHE_GEN="20260929-lkg1956-r1"
TMP="$(mktemp)"
PUBLIC_HTML="$(mktemp)"
PUBLIC_LOADER="$(mktemp)"
PUBLIC_CSS="$(mktemp)"
PUBLIC_VOICE="$(mktemp)"
trap 'rm -f "$TMP" "$PUBLIC_HTML" "$PUBLIC_LOADER" "$PUBLIC_CSS" "$PUBLIC_VOICE"' EXIT

curl -fsSL --retry 3 --connect-timeout 10 "$RAW" -o "$TMP"
python3 "$TMP"

test -x "$RESTART" || {
  echo "LKG_1956=FAIL restart_script_missing"
  exit 2
}

"$RESTART"

code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18080/health || true)"
[ "$code" = "200" ] || {
  echo "LKG_1956=FAIL local_health_http=$code"
  exit 2
}

probe="https://powerpc-darwin.org/?__lkg1956_probe=$(date +%s)"
curl -fsSL --retry 3 --connect-timeout 10 --max-time 25   -H 'Cache-Control: no-cache'   -H 'Pragma: no-cache'   "$probe" -o "$PUBLIC_HTML" || {
    echo "LKG_1956=FAIL public_html_fetch"
    exit 2
  }

grep -Fq "/static/loader.js?v=$CACHE_GEN" "$PUBLIC_HTML" || {
  echo "LKG_1956=FAIL public_loader_generation_missing"
  exit 2
}
grep -Fq "/static/custom.css?v=$CACHE_GEN" "$PUBLIC_HTML" || {
  echo "LKG_1956=FAIL public_css_generation_missing"
  exit 2
}

if grep -Fq 'owui-pwa-legacy-chats-bypass-v20260929.5' "$PUBLIC_HTML"; then
  echo "LKG_1956=FAIL stale_v5_guard_present"
  exit 2
fi
if grep -Fq 'owui-pwa-startup-guard-v20260929.6' "$PUBLIC_HTML"; then
  echo "LKG_1956=FAIL stale_v6_guard_present"
  exit 2
fi
if grep -Fq '.pwa20260929_6.js' "$PUBLIC_HTML"; then
  echo "LKG_1956=FAIL stale_v6_entry_present"
  exit 2
fi

for name in pwa-client-runtime.js pwa-voice-bridge.js lcars-runtime.js continuity-shell-registry.js continuity-controls.js continuity-settings.js; do
  if grep -Eq "<script[^>]+src=[\"'][^\"']*/static/$name([?\"'])" "$PUBLIC_HTML"; then
    echo "LKG_1956=FAIL direct_post_isolation_script_present=$name"
    exit 2
  fi
done

curl -fsSL --retry 3 --max-time 20   "https://powerpc-darwin.org/static/loader.js?v=$CACHE_GEN&cb=$(date +%s)" -o "$PUBLIC_LOADER"
curl -fsSL --retry 3 --max-time 20   "https://powerpc-darwin.org/static/custom.css?v=$CACHE_GEN&cb=$(date +%s)" -o "$PUBLIC_CSS"
curl -fsSL --retry 3 --max-time 20   "https://powerpc-darwin.org/static/pwa-voice-bridge.js?cb=$(date +%s)" -o "$PUBLIC_VOICE"

loader_sha="$(sha256sum "$PUBLIC_LOADER" | awk '{print $1}')"
css_sha="$(sha256sum "$PUBLIC_CSS" | awk '{print $1}')"
voice_sha="$(sha256sum "$PUBLIC_VOICE" | awk '{print $1}')"

[ "$loader_sha" = "e101590a26011b7d804470936333075dc97c20131e7d70bffd889754b35e2f39" ] || {
  echo "LKG_1956=FAIL public_loader_sha256=$loader_sha"
  exit 2
}
[ "$css_sha" = "475abc34859bc632461e6bd66bef2e2893fdc8e108035ce5a0617461a6469484" ] || {
  echo "LKG_1956=FAIL public_css_sha256=$css_sha"
  exit 2
}
[ "$voice_sha" = "ad38be628a364e50f4f495970b0c2381bc10ac2f64e3acf8bf8f0313fa14b0f6" ] || {
  echo "LKG_1956=FAIL public_voice_sha256=$voice_sha"
  exit 2
}

grep -Fq 'window.__CONTINUITY_BOOTSTRAP_ISOLATED__ = true' "$PUBLIC_LOADER" || {
  echo "LKG_1956=FAIL public_isolation_marker_missing"
  exit 2
}

app="$(python3 - "$PUBLIC_HTML" <<'PY'
import re, sys
s=open(sys.argv[1]).read()
m=re.search(r'/_app/immutable/entry/app\.[A-Za-z0-9_-]+\.js', s)
print(m.group(0) if m else '')
PY
)"
[ -n "$app" ] || {
  echo "LKG_1956=FAIL stock_app_entry_missing"
  exit 2
}
app_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://powerpc-darwin.org$app?cb=$(date +%s)" || true)"
[ "$app_code" = "200" ] || {
  echo "LKG_1956=FAIL stock_app_http=$app_code"
  exit 2
}

echo "LKG_1956=PUBLIC_PASS"
echo "local_health_http=$code"
echo "cache_generation=$CACHE_GEN"
echo "loader_sha256=$loader_sha"
echo "custom_css_sha256=$css_sha"
echo "voice_bridge_sha256=$voice_sha"
echo "stock_app=$app"
echo "stock_app_http=$app_code"
echo "NEXT=DEVICE_FORCE_CLOSE_REOPEN_EXISTING_HOME_SCREEN_PWA"
