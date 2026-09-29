#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
RESTART="$BASE/restart-openwebui-via-passenger.sh"
PIN="355a6eed5da15c3a4750936238dbaa35013b99fc"
RAW="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PIN/bootstrap-relay/pwa-backup-bisect/backup_stepper.py"

TMP="$(mktemp)"
OUT="$(mktemp)"
PUBLIC="$(mktemp)"
trap 'rm -f "$TMP" "$OUT" "$PUBLIC"' EXIT

curl -fsSL --retry 3 --connect-timeout 10 "$RAW" -o "$TMP"

python3 "$TMP" --next | tee "$OUT"

TAG="$(awk -F= '/^TAG=/{print $2}' "$OUT" | tail -1)"
CANDIDATE="$(awk '/^CANDIDATE=/{sub(/^CANDIDATE=/,"");print}' "$OUT" | tail -1)"
KEY="$(awk -F= '/^KEY=/{print $2}' "$OUT" | tail -1)"

[ -n "$TAG" ] || {
  echo "BACKUP_BISECT=FAIL missing_tag"
  python3 "$TMP" --abort || true
  exit 2
}
[ -n "$CANDIDATE" ] || {
  echo "BACKUP_BISECT=FAIL missing_candidate"
  python3 "$TMP" --abort || true
  exit 2
}

rollback_and_fail() {
  reason="$1"
  echo "BACKUP_BISECT=FAIL $reason"
  python3 "$TMP" --abort || true
  if [ -x "$RESTART" ]; then
    "$RESTART" || true
  fi
  exit 2
}

test -x "$RESTART" || rollback_and_fail "restart_script_missing"

"$RESTART" || rollback_and_fail "restart_failed"

code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18080/health || true)"
[ "$code" = "200" ] || rollback_and_fail "local_health_http=$code"

probe="https://powerpc-darwin.org/?__backup_bisect=$TAG-$(date +%s)"
curl -fsSL --retry 3 --connect-timeout 10 --max-time 25 \
  -H 'Cache-Control: no-cache' \
  -H 'Pragma: no-cache' \
  "$probe" -o "$PUBLIC" || rollback_and_fail "public_html_fetch"

grep -Fq "owui-backup-bisect:$TAG" "$PUBLIC" || rollback_and_fail "public_marker_missing"
grep -Fq "?rb=$TAG" "$PUBLIC" || rollback_and_fail "public_cache_generation_missing"

python3 "$TMP" --commit

echo "BACKUP_BISECT=PUBLIC_PASS"
echo "candidate=$CANDIDATE"
echo "key=$KEY"
echo "tag=$TAG"
echo "local_health_http=$code"
echo "NEXT=DEVICE_FORCE_CLOSE_REOPEN_EXISTING_HOME_SCREEN_PWA"
echo "IF_STILL_BROKEN=RUN_THIS_SAME_COMMAND_AGAIN_TO_MOVE_TO_NEXT_OLDER_BACKUP"
