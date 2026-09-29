#!/usr/bin/env bash
set -euo pipefail

BASE="https://powerpc-darwin.org"
COOKIE_JAR="/tmp/ppc-gate.cookies"
RECOVERY_BODY="/tmp/ppc-gate-recovery.txt"
CREATE_JSON="/tmp/ppc-terminal-create.json"
OUTPUT_JSON="/tmp/ppc-terminal-output.json"
TERM_OUT="/tmp/ppc-terminal.out"
SID=""
CSRF=""
CURSOR=0

cleanup() {
  if [[ -n "${SID:-}" && -n "${CSRF:-}" && -s "$COOKIE_JAR" ]]; then
    curl -sS --connect-timeout 5 --max-time 15 -b "$COOKIE_JAR"       -X DELETE -H "X-Terminal-CSRF: $CSRF"       "$BASE/terminal/api/session/$SID" >/dev/null 2>&1 || true
  fi
  rm -f "$COOKIE_JAR" "$RECOVERY_BODY" "$CREATE_JSON" "$OUTPUT_JSON" "$TERM_OUT"         /tmp/ppc-input.json /tmp/ppc-status.json /tmp/ppc-identity.json
}
trap cleanup EXIT

recover_gate() {
  local token_url=""
  local candidate code
  for candidate in     "/recover-openwebui-proxy-gate-v1.php"     "/recover-openwebui-proxy-gate-v1%281%29.php"     "/recover-openwebui-proxy-gate-v1%282%29.php"     "/recover-openwebui-proxy-gate-v1%283%29.php"
  do
    code="$(curl --globoff -sS --connect-timeout 10 --max-time 30       -o "$RECOVERY_BODY" -w '%{http_code}' "$BASE$candidate" || true)"
    if [[ "$code" == "200" ]] && grep -q 'FRESH ONE-TIME BOOTSTRAP URL:' "$RECOVERY_BODY"; then
      token_url="$(grep -Eo 'https://powerpc-darwin\.org/__owui_gate\?token=[A-Za-z0-9_-]+' "$RECOVERY_BODY" | tail -n1 || true)"
      if [[ -n "$token_url" ]]; then
        break
      fi
    fi
  done

  if [[ -z "$token_url" ]]; then
    echo "GATE_RECOVERY=UNAVAILABLE"
    return 30
  fi

  local token="${token_url##*token=}"
  echo "::add-mask::$token"
  local gate_code
  gate_code="$(curl -sS -L --connect-timeout 10 --max-time 30     -c "$COOKIE_JAR" -b "$COOKIE_JAR" -o /dev/null -w '%{http_code}' "$token_url" || true)"
  unset token token_url
  rm -f "$RECOVERY_BODY"

  if [[ "$gate_code" != "200" ]] || ! grep -q '__Host-owui_gate' "$COOKIE_JAR"; then
    echo "GATE_RECOVERY=EXCHANGE_FAIL"
    echo "GATE_EXCHANGE_HTTP=$gate_code"
    return 31
  fi
  echo "GATE_RECOVERY=PASS"
}

create_terminal() {
  local body='{"cols":100,"rows":30}'
  local code
  code="$(curl -sS --connect-timeout 10 --max-time 30     -b "$COOKIE_JAR" -o "$CREATE_JSON" -w '%{http_code}'     -H 'Content-Type: application/json' -d "$body"     "$BASE/terminal/api/session" || true)"

  if [[ "$code" == "409" ]]; then
    body='{"cols":100,"rows":30,"resume_existing":true}'
    code="$(curl -sS --connect-timeout 10 --max-time 30       -b "$COOKIE_JAR" -o "$CREATE_JSON" -w '%{http_code}'       -H 'Content-Type: application/json' -d "$body"       "$BASE/terminal/api/session" || true)"
  fi

  if [[ "$code" != "200" ]]; then
    echo "TERMINAL_CREATE_HTTP=$code"
    echo "TERMINAL_MACHINE_CALLABLE=FAIL"
    return 32
  fi

  SID="$(python3 -c 'import json; d=json.load(open("'"$CREATE_JSON"'")); print(d["session_id"])')"
  CSRF="$(python3 -c 'import json; d=json.load(open("'"$CREATE_JSON"'")); print(d["csrf_token"])')"
  CURSOR="$(python3 -c 'import json; d=json.load(open("'"$CREATE_JSON"'")); print(int(d.get("cursor",0)))')"
  echo "::add-mask::$SID"
  echo "::add-mask::$CSRF"
  : > "$TERM_OUT"
  echo "TERMINAL_MACHINE_CALLABLE=PASS"
}

send_text() {
  local text="$1"
  local payload req code
  payload="$(printf '%s\r' "$text" | base64 -w0)"
  req="$(python3 -c 'import json,sys; print(json.dumps({"data_b64":sys.argv[1]},separators=(",",":")))' "$payload")"
  code="$(curl -sS --connect-timeout 10 --max-time 30     -b "$COOKIE_JAR" -o /tmp/ppc-input.json -w '%{http_code}'     -H 'Content-Type: application/json'     -H "X-Terminal-CSRF: $CSRF"     -d "$req" "$BASE/terminal/api/session/$SID/input" || true)"
  [[ "$code" == "200" ]] || {
    echo "TERMINAL_INPUT=FAIL http=$code"
    return 33
  }
}

poll_until() {
  local marker="$1"
  local max_seconds="${2:-210}"
  local deadline=$((SECONDS + max_seconds))
  local code data
  while (( SECONDS < deadline )); do
    code="$(curl -sS --connect-timeout 10 --max-time 20       -b "$COOKIE_JAR" -o "$OUTPUT_JSON" -w '%{http_code}'       -H "X-Terminal-CSRF: $CSRF"       "$BASE/terminal/api/session/$SID/output?cursor=$CURSOR" || true)"
    if [[ "$code" == "200" ]]; then
      data="$(python3 -c 'import json; d=json.load(open("'"$OUTPUT_JSON"'")); print(d.get("data_b64",""))')"
      CURSOR="$(python3 -c 'import json; d=json.load(open("'"$OUTPUT_JSON"'")); print(int(d.get("next_cursor",0)))')"
      if [[ -n "$data" ]]; then
        printf '%s' "$data" | base64 -d >> "$TERM_OUT"
      fi
      if grep -aFq "$marker" "$TERM_OUT"; then
        return 0
      fi
    fi
    sleep 1
  done
  return 1
}

destroy_terminal() {
  local code
  code="$(curl -sS --connect-timeout 10 --max-time 20     -b "$COOKIE_JAR" -o /tmp/ppc-delete.json -w '%{http_code}'     -X DELETE -H "X-Terminal-CSRF: $CSRF"     "$BASE/terminal/api/session/$SID" || true)"
  rm -f /tmp/ppc-delete.json
  if [[ "$code" != "200" ]]; then
    echo "TERMINAL_DESTROY_HTTP=$code"
    return 34
  fi
  SID=""
  CSRF=""
  echo "ORIGINATING_TERMINAL_DESTROYED=PASS"
}

recover_gate
create_terminal

REMOTE_CMD='set +e; TMP="$(mktemp)"; URL="https://raw.githubusercontent.com/Christopher-Charman/open-webui/daaa4e3226e81788858eb3d209d956d728347c93/bootstrap-relay/permanent-control/bootstrap-control-plane.sh"; curl -fsSL --retry 4 "$URL" -o "$TMP"; FRC=$?; BRC=127; if [ "$FRC" -eq 0 ]; then chmod 700 "$TMP"; sh -n "$TMP"; SRC=$?; if [ "$SRC" -eq 0 ]; then "$TMP"; BRC=$?; else BRC=$SRC; fi; else BRC=$FRC; fi; rm -f "$TMP"; echo CONTROL_BOOTSTRAP_EXEC_RC=$BRC; if [ -x /home/storage/781/4477781/user/webapp/bin/powerpc-control ]; then /home/storage/781/4477781/user/webapp/bin/powerpc-control restart; echo OWNED_RECEIVER_RESTART_RC=$?; sleep 3; /home/storage/781/4477781/user/webapp/bin/powerpc-control status; echo OWNED_RECEIVER_STATUS_RC=$?; else echo OWNED_RECEIVER_BINARY=MISSING; fi; if [ -x /home/storage/781/4477781/user/webapp/bin/secure-mcp-keepalive ]; then /home/storage/781/4477781/user/webapp/bin/secure-mcp-keepalive status; echo SECURE_MCP_STATUS_RC=$?; else echo SECURE_MCP_KEEPALIVE_BINARY=MISSING; fi; M="CONTROL_BOOTSTRAP_TERMINAL_PHASE_""COMPLETE"; echo "$M"'
send_text "$REMOTE_CMD"

if ! poll_until "CONTROL_BOOTSTRAP_TERMINAL_PHASE_COMPLETE" 240; then
  echo "CONTROL_BOOTSTRAP_TERMINAL_PHASE=TIMEOUT"
  exit 35
fi

for marker in   "OWNED_RECEIVER_HOST=PASS"   "SECURE_MCP_LIFECYCLE_HOST=PASS"   "SECURE_MCP_LIFECYCLE_HOST=PARTIAL"   "POWERPC_CONTROL=RUNNING"   "SECURE_MCP_KEEPALIVE=HEALTHY"   "CONTROL_BOOTSTRAP_EXEC_RC="   "OWNED_RECEIVER_RESTART_RC="   "OWNED_RECEIVER_STATUS_RC="   "SECURE_MCP_STATUS_RC="
do
  grep -aF "$marker" "$TERM_OUT" | tail -n1 || true
done

if ! grep -aFq "OWNED_RECEIVER_HOST=PASS" "$TERM_OUT"; then
  echo "OWNED_RECEIVER_INSTALL_ACCEPTANCE=FAIL"
  exit 36
fi
if ! grep -aFq "POWERPC_CONTROL=RUNNING" "$TERM_OUT"; then
  echo "OWNED_RECEIVER_RUNTIME=FAIL"
  exit 37
fi
echo "OWNED_RECEIVER_RUNTIME=PASS"

identity_code="$(curl -sS --connect-timeout 10 --max-time 25   -o /tmp/ppc-identity.json -w '%{http_code}'   "$BASE/static/powerpc-control-v1/identity.json?t=$(date +%s)" || true)"
echo "PUBLIC_IDENTITY_HTTP=$identity_code"
if [[ "$identity_code" != "200" ]] || ! python3 -c 'import json; d=json.load(open("/tmp/ppc-identity.json")); assert d.get("protocol")=="powerpc-control-v1"; assert d.get("runtime_id")=="fasthost.powerpc"; assert d.get("state")=="ready"; assert d.get("uid")==2257347; assert d.get("hostname")=="hp3-rr-1024747.hostingp3.local"'; then
  echo "PUBLIC_IDENTITY=FAIL"
  exit 38
fi
echo "PUBLIC_IDENTITY=PASS"
python3 -c 'import json; d=json.load(open("/tmp/ppc-identity.json")); print("identity_fingerprint="+d["identity_fingerprint"])'

destroy_terminal
rm -f "$COOKIE_JAR"
echo "BROWSER_COOKIE_INDEPENDENCE_TEST=START"
sleep 40

status_code="$(curl -sS --connect-timeout 10 --max-time 25   -o /tmp/ppc-status.json -w '%{http_code}'   "$BASE/static/powerpc-control-v1/status.json?t=$(date +%s)" || true)"
echo "POST_DESTROY_STATUS_HTTP=$status_code"
if [[ "$status_code" != "200" ]] || ! python3 -c 'import json,time; d=json.load(open("/tmp/ppc-status.json")); assert d.get("protocol")=="powerpc-control-v1"; assert d.get("runtime_id")=="fasthost.powerpc"; assert d.get("state")=="ready"; assert int(time.time())-int(d.get("heartbeat_at",0)) < 90'; then
  echo "POST_TERMINAL_RECEIVER_SURVIVAL=FAIL"
  exit 39
fi
echo "POST_TERMINAL_RECEIVER_SURVIVAL=PASS"
echo "BROWSER_COOKIE_INDEPENDENCE=PASS"
echo "BOOTSTRAP_PHASE=HOST_PASS"
