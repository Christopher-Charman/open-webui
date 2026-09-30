#!/bin/sh
set -eu
umask 077

ACCOUNT="/home/storage/781/4477781/user"
WEBAPP="$ACCOUNT/webapp"
STATE="$ACCOUNT/.powerpc-control-v1"
DAEMON="$STATE/daemon.py"
SERVICE="$WEBAPP/bin/powerpc-control"
SOURCE_COMMIT="914c6757f7c0dd16dd6e927d27996bc1b263ef40"
SOURCE="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$SOURCE_COMMIT/bootstrap-relay/permanent-control/daemon.py"

fail() {
  echo "OWNED_RECEIVER_HOST=FAIL reason=$1" >&2
  exit 1
}

[ "$(id -u)" = "2257347" ] || fail runtime_identity
[ -d "$WEBAPP" ] || fail webapp_missing
[ -d "$STATE" ] || fail receiver_state_missing
[ -x "$SERVICE" ] || fail receiver_service_missing
[ -f "$STATE/x25519-private.pem" ] || fail x25519_key_missing
[ -f "$STATE/ed25519-private.pem" ] || fail ed25519_key_missing

PY=""
for p in "$WEBAPP/miniconda/bin/python3.12" "$WEBAPP/miniconda/bin/python3" "$WEBAPP/envs/open-terminal/bin/python"; do
  if [ -x "$p" ]; then PY="$p"; break; fi
done
[ -n "$PY" ] || fail python_missing

STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
TMP="$STATE/daemon.py.receiver-recovery.$$"
BACKUP="$STATE/daemon.py.pre-receiver-recovery-$STAMP.bak"
cleanup() { rm -f "$TMP" "$TMP"c; }
trap cleanup EXIT

curl -fsSL --retry 4 --connect-timeout 10 "$SOURCE" -o "$TMP" || fail download
chmod 700 "$TMP"
"$PY" -m py_compile "$TMP" || fail compile
grep -Fq 'powerpc-control-result-' "$TMP" || fail canonical_alias_missing
grep -Fq 'ppc-control-result-' "$TMP" || fail compatibility_alias_missing

cp -p "$DAEMON" "$BACKUP"
chmod 600 "$BACKUP"
mv -f "$TMP" "$DAEMON"
chmod 700 "$DAEMON"

if ! "$SERVICE" restart; then
  cp -p "$BACKUP" "$DAEMON"
  chmod 700 "$DAEMON"
  "$SERVICE" restart >/dev/null 2>&1 || true
  fail restart_rolled_back
fi

sleep 3
"$SERVICE" status || fail status
DAEMON_SHA256="$(sha256sum "$DAEMON" | awk '{print $1}')"

echo "OWNED_RECEIVER_HOST=PASS"
echo "POWERPC_RECEIVER_SOURCE_COMMIT=$SOURCE_COMMIT"
echo "POWERPC_RECEIVER_DAEMON_SHA256=$DAEMON_SHA256"
echo "POWERPC_RECEIVER_CANONICAL_FLAT_ALIAS=PASS"
echo "POWERPC_RECEIVER_COMPAT_FLAT_ALIAS=PASS"
echo "OPENWEBUI_RESTARTED=NO"
