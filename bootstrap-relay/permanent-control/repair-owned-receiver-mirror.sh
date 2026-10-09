#!/bin/sh
set -eu
umask 077

ACCOUNT="${PPC_ACCOUNT:-${HOME}}"
WEBAPP="$ACCOUNT/webapp"
STATE="$ACCOUNT/.powerpc-control-v1"
SERVICE="$WEBAPP/bin/powerpc-control"
DAEMON="$STATE/daemon.py"
MIRROR="$WEBAPP/envs/openwebui/lib/python3.11/site-packages/open_webui/static/powerpc-control-v1"
PIN="c123b142b9e19f5c85e471345a1f965db1073c89"
SOURCE="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/permanent-control/daemon.py"

fail() {
  echo "OWNED_RECEIVER_MIRROR=FAIL reason=$1" >&2
  exit 1
}

[ "$(id -u)" = "2257347" ] || fail "runtime_identity"
[ -d "$WEBAPP" ] || fail "webapp_missing"
[ -d "$STATE" ] || fail "receiver_state_missing"
[ -x "$SERVICE" ] || fail "receiver_service_missing"
[ -f "$STATE/x25519-private.pem" ] || fail "x25519_key_missing"
[ -f "$STATE/ed25519-private.pem" ] || fail "ed25519_key_missing"

PY=""
for p in "$WEBAPP/miniconda/bin/python3.12" "$WEBAPP/miniconda/bin/python3" "$WEBAPP/envs/open-terminal/bin/python"; do
  if [ -x "$p" ]; then PY="$p"; break; fi
done
[ -n "$PY" ] || fail "python_missing"

STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
BACKUP="$STATE/daemon.py.pre-static-mirror-$STAMP.bak"
TMP="$STATE/daemon.py.mirror.$$"

cleanup() { rm -f "$TMP" "$TMP"c; }
trap cleanup EXIT

curl -fsSL --retry 4 --connect-timeout 10 "$SOURCE" -o "$TMP" || fail "download"
chmod 700 "$TMP"
"$PY" -m py_compile "$TMP" || fail "compile"

grep -Fq 'PUBLIC_MIRROR = Path' "$TMP" || fail "mirror_marker_missing"
grep -Fq 'MIRROR_RESULTS = PUBLIC_MIRROR / "results"' "$TMP" || fail "mirror_results_marker_missing"

cp -p "$DAEMON" "$BACKUP"
chmod 600 "$BACKUP"
mv -f "$TMP" "$DAEMON"
chmod 700 "$DAEMON"

if ! "$SERVICE" restart; then
  cp -p "$BACKUP" "$DAEMON"
  chmod 700 "$DAEMON"
  "$SERVICE" restart >/dev/null 2>&1 || true
  fail "receiver_restart"
fi

deadline=$(( $(date +%s) + 60 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  if [ -s "$MIRROR/identity.json" ] && [ -s "$MIRROR/status.json" ]; then
    if "$PY" - "$MIRROR/identity.json" "$MIRROR/status.json" <<'PY'
import json,sys,time
i=json.load(open(sys.argv[1]))
s=json.load(open(sys.argv[2]))
assert i.get("protocol")=="powerpc-control-v1"
assert i.get("runtime_id")=="fasthost.powerpc"
assert i.get("uid")==2257347
assert i.get("hostname")=="hp3-rr-1024747.hostingp3.local"
assert i.get("state")=="ready"
assert s.get("protocol")=="powerpc-control-v1"
assert s.get("runtime_id")=="fasthost.powerpc"
assert s.get("state")=="ready"
assert int(time.time())-int(s.get("heartbeat_at",0)) < 90
PY
    then
      break
    fi
  fi
  sleep 2
done

[ -s "$MIRROR/identity.json" ] || {
  cp -p "$BACKUP" "$DAEMON"
  chmod 700 "$DAEMON"
  "$SERVICE" restart >/dev/null 2>&1 || true
  fail "identity_mirror_missing"
}
[ -s "$MIRROR/status.json" ] || fail "status_mirror_missing"

"$SERVICE" status >/dev/null || fail "receiver_status"

LOCAL_CODE="$(curl -sS --connect-timeout 5 --max-time 15 -o "$STATE/mirror-local-check.$$" -w '%{http_code}'   -H 'Host: powerpc-darwin.org'   http://127.0.0.1:18080/static/powerpc-control-v1/identity.json || true)"
if [ "$LOCAL_CODE" != "200" ]; then
  rm -f "$STATE/mirror-local-check.$$"
  fail "local_static_http_$LOCAL_CODE"
fi
"$PY" - "$STATE/mirror-local-check.$$" <<'PY' || fail "local_static_not_identity"
import json,sys
d=json.load(open(sys.argv[1]))
assert d.get("protocol")=="powerpc-control-v1"
assert d.get("runtime_id")=="fasthost.powerpc"
assert d.get("uid")==2257347
PY
rm -f "$STATE/mirror-local-check.$$"

echo "OWNED_RECEIVER_MIRROR=PASS"
echo "receiver=fasthost.powerpc"
echo "source_commit=$PIN"
echo "keys=PRESERVED"
echo "state_db=PRESERVED"
echo "service=DETACHED_CRON_ENSURE"
echo "static_identity=PASS"
echo "NEXT=AUTONOMOUS_ORIGIN_ACCEPTANCE"
