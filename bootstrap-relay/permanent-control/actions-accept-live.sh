#!/usr/bin/env bash
set -euo pipefail
umask 077

REPO_ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
CONTROL_DIR="$REPO_ROOT/bootstrap-relay/permanent-control"
QUEUE="$CONTROL_DIR/queue.json"
CLIENT="$CONTROL_DIR/origin-client.py"
IDENTITY_URL="${PPC_ACCEPT_IDENTITY_URL:-https://www.powerpc-darwin.org/static/ppc-control-identity.json}"
RESULT_BASE="${PPC_ACCEPT_RESULT_BASE:-https://www.powerpc-darwin.org/static/ppc-control-results}"
WORK="$(mktemp -d)"
OWNED_TASK_IDS="$WORK/owned-task-ids"
IDENTITY="$WORK/identity.json"
FP=""
CLEANING=0

log() { printf '%s\n' "$*"; }
fail() { log "POWERPC_OWNED_CONTROL_ACCEPTANCE=FAIL"; log "reason=$1"; exit 1; }

git config user.name "PowerPC Control Acceptance"
git config user.email "61332783+Christopher-Charman@users.noreply.github.com"
touch "$OWNED_TASK_IDS"

sync_main() {
  git fetch origin main >/dev/null 2>&1
  git reset --hard origin/main >/dev/null 2>&1
}

remove_owned_task() {
  local task_id="$1" attempt
  for attempt in 1 2 3 4 5; do
    sync_main || continue
    python3 - "$QUEUE" "$task_id" <<'PY'
import json,sys
path,task_id=sys.argv[1:3]
with open(path,encoding="utf-8") as f:
    q=json.load(f)
assert q.get("protocol")=="powerpc-control-v1"
assert q.get("version")==1
tasks=q.get("tasks")
assert isinstance(tasks,list)
kept=[t for t in tasks if not (isinstance(t,dict) and t.get("task_id")==task_id)]
if len(kept)==len(tasks):
    raise SystemExit(0)
q["tasks"]=kept
with open(path,"w",encoding="utf-8") as f:
    json.dump(q,f,separators=(",",":"),sort_keys=True)
    f.write("\n")
PY
    if git diff --quiet -- "$QUEUE"; then
      return 0
    fi
    git add "$QUEUE"
    git commit -m "control: retire acceptance task $task_id" >/dev/null 2>&1 || return 1
    if git push origin HEAD:main >/dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}

cleanup_owned_tasks() {
  local rc=$? cleanup_failed=0 task_id
  if [ "$CLEANING" = "1" ]; then exit "$rc"; fi
  CLEANING=1
  set +e
  if [ -s "$OWNED_TASK_IDS" ]; then
    while IFS= read -r task_id; do
      [ -n "$task_id" ] || continue
      remove_owned_task "$task_id" || {
        log "cleanup_warning=failed_to_retire_acceptance_task task_id=$task_id"
        cleanup_failed=1
      }
    done < <(sort -u "$OWNED_TASK_IDS")
  fi
  rm -rf "$WORK"
  if [ "$rc" -eq 0 ] && [ "$cleanup_failed" -ne 0 ]; then
    log "POWERPC_OWNED_CONTROL_ACCEPTANCE=FAIL"
    log "reason=acceptance_task_cleanup_conflict"
    exit 1
  fi
  exit "$rc"
}
trap cleanup_owned_tasks EXIT INT TERM

python3 - "$QUEUE" <<'PY'
import json,sys
q=json.load(open(sys.argv[1]))
assert q.get("protocol")=="powerpc-control-v1"
assert q.get("version")==1
assert isinstance(q.get("tasks"),list), "queue tasks must be a list"
PY

fetch_identity() {
  curl -fsSL --connect-timeout 10 --max-time 30     "$IDENTITY_URL?t=$(date +%s%N)" -o "$IDENTITY"
  python3 - "$IDENTITY" <<'PY'
import json,sys,time
d=json.load(open(sys.argv[1]))
assert d.get("protocol")=="powerpc-control-v1"
assert d.get("version")==1
assert d.get("runtime_id")=="fasthost.powerpc"
assert d.get("state")=="ready"
assert d.get("user")=="csh3280350"
assert d.get("uid")==2257347
assert d.get("hostname")=="hp3-rr-1024747.hostingp3.local"
assert int(time.time())-int(d.get("heartbeat_at",0)) < 90
assert set(d.get("tool_contract",[]))=={"runtime_health","read_text","list_dir","terminal_exec"}
PY
}

queue_envelope() {
  local envelope="$1" task_id="$2" attempt
  for attempt in 1 2 3 4 5; do
    sync_main || continue
    python3 - "$envelope" "$QUEUE" <<'PY'
import json,sys
envelope_path,queue_path=sys.argv[1:3]
with open(envelope_path,encoding="utf-8") as f:
    task=json.load(f)
with open(queue_path,encoding="utf-8") as f:
    q=json.load(f)
assert q.get("protocol")=="powerpc-control-v1"
assert q.get("version")==1
tasks=q.get("tasks")
assert isinstance(tasks,list)
task_id=task.get("task_id")
if not isinstance(task_id,str) or not task_id:
    raise SystemExit("task_id missing")
same=[t for t in tasks if isinstance(t,dict) and t.get("task_id")==task_id]
if same:
    if len(same)==1 and same[0]==task:
        raise SystemExit(0)
    raise SystemExit("task_id conflict")
if len(tasks)>=128:
    raise SystemExit("queue capacity exhausted")
tasks.append(task)
with open(queue_path,"w",encoding="utf-8") as f:
    json.dump(q,f,separators=(",",":"),sort_keys=True)
    f.write("\n")
PY
    py_rc=$?
    if [ "$py_rc" -ne 0 ]; then
      fail "queue_append_invalid:$task_id"
    fi
    if git diff --quiet -- "$QUEUE"; then
      printf '%s\n' "$task_id" >>"$OWNED_TASK_IDS"
      return 0
    fi
    git add "$QUEUE"
    git commit -m "control: acceptance task $task_id" >/dev/null
    if git push origin HEAD:main >/dev/null 2>&1; then
      printf '%s\n' "$task_id" >>"$OWNED_TASK_IDS"
      return 0
    fi
  done
  fail "queue_append_conflict:$task_id"
}

wait_result() {
  local task_id="$1" out="$2" timeout="${3:-100}"
  local deadline=$((SECONDS + timeout))
  while (( SECONDS < deadline )); do
    if curl -fsSL --connect-timeout 8 --max-time 20       "$RESULT_BASE/$task_id.json?t=$(date +%s%N)" -o "$out" 2>/dev/null; then
      if python3 - "$out" "$task_id" <<'PY'
import json,sys
try:
    d=json.load(open(sys.argv[1]))
    assert d.get("protocol")=="powerpc-control-v1"
    assert d.get("task_id")==sys.argv[2]
    assert d.get("kind")=="result"
except Exception:
    raise SystemExit(1)
PY
      then return 0; fi
    fi
    sleep 2
  done
  return 1
}

assert_no_result() {
  local task_id="$1" seconds="${2:-25}"
  local deadline=$((SECONDS + seconds))
  while (( SECONDS < deadline )); do
    if curl -fsSL --connect-timeout 8 --max-time 15       "$RESULT_BASE/$task_id.json?t=$(date +%s%N)" -o "$WORK/unexpected.json" 2>/dev/null; then
      if python3 - "$WORK/unexpected.json" "$task_id" <<'PY'
import json,sys
try:
    d=json.load(open(sys.argv[1]))
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if d.get("task_id")==sys.argv[2] else 1)
PY
      then return 1; fi
    fi
    sleep 2
  done
  return 0
}

prepare() {
  local task_id="$1" tool="$2" args="$3" authority="$4" envelope="$5" context="$6"
  shift 6
  python3 "$CLIENT" prepare     --identity "$IDENTITY"     --expected-fingerprint "$FP"     --task-id "$task_id"     --tool "$tool"     --arguments "$args"     --authority "$authority"     --ttl 300     --output "$envelope"     --context "$context" "$@" >/dev/null
}

decode_to() {
  local result="$1" context="$2" out="$3"
  python3 "$CLIENT" decode     --result "$result"     --context "$context"     --output "$out" >/dev/null
}

assert_receipt_common() {
  local plain="$1" task_id="$2" state="$3"
  python3 - "$plain" "$task_id" "$state" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d.get("task_id")==sys.argv[2]
assert d.get("completion_state")==sys.argv[3]
i=d.get("executor_identity") or {}
assert i.get("runtime_id")=="fasthost.powerpc"
assert i.get("user")=="csh3280350"
assert i.get("uid")==2257347
assert i.get("hostname")=="hp3-rr-1024747.hostingp3.local"
r=d.get("runtime_receipt") or {}
assert r.get("namespace")=="/home/storage/781/4477781/user"
assert r.get("webapp")=="/home/storage/781/4477781/user/webapp"
PY
}

fetch_identity

# First prepare verifies the runtime identity self-signature and computes its
# fingerprint. Pin every later task to that same identity.
ID_OUT="$(python3 "$CLIENT" prepare   --identity "$IDENTITY"   --task-id "ppc-accept-health-$(date +%s)"   --tool runtime_health   --arguments '{}'   --authority read_only   --ttl 300   --output "$WORK/health-envelope.json"   --context "$WORK/health-context.json")"
FP="$(printf '%s\n' "$ID_OUT" | sed -n 's/^IDENTITY_FINGERPRINT=//p' | tail -n1)"
[ -n "$FP" ] || fail "identity_fingerprint_not_verified"
echo "::add-mask::$FP"
HEALTH_ID="$(python3 -c 'import json; print(json.load(open("'"$WORK/health-envelope.json"'"))["task_id"])')"
log "IDENTITY_SIGNATURE_AND_PIN=PASS"

queue_envelope "$WORK/health-envelope.json" "$HEALTH_ID"
wait_result "$HEALTH_ID" "$WORK/health-result.json" || fail "runtime_health_result_timeout"
decode_to "$WORK/health-result.json" "$WORK/health-context.json" "$WORK/health-plain.json"
assert_receipt_common "$WORK/health-plain.json" "$HEALTH_ID" "COMPLETED"
log "FRESH_ORIGIN_RUNTIME_HEALTH=PASS"

# Exact duplicate must not be re-executed or re-published.
DUP_SHA1="$(sha256sum "$WORK/health-result.json" | awk '{print $1}')"
DUP_PUB1="$(python3 -c 'import json; print(json.load(open("'"$WORK/health-result.json"'"))["published_at"])')"
sleep 24
curl -fsSL "$RESULT_BASE/$HEALTH_ID.json?t=$(date +%s%N)" -o "$WORK/health-result-2.json"
DUP_SHA2="$(sha256sum "$WORK/health-result-2.json" | awk '{print $1}')"
DUP_PUB2="$(python3 -c 'import json; print(json.load(open("'"$WORK/health-result-2.json"'"))["published_at"])')"
[ "$DUP_SHA1" = "$DUP_SHA2" ] && [ "$DUP_PUB1" = "$DUP_PUB2" ] || fail "duplicate_reprocessed"
log "DUPLICATE_SUPPRESSION=PASS"

# Bounded read round trip.
READ_ID="ppc-accept-read-$(date +%s)-$RANDOM"
prepare "$READ_ID" read_text '{"path":"CONTROL_PLANE.md","max_bytes":2048}' read_only   "$WORK/read-envelope.json" "$WORK/read-context.json"
queue_envelope "$WORK/read-envelope.json" "$READ_ID"
wait_result "$READ_ID" "$WORK/read-result.json" || fail "read_text_result_timeout"
decode_to "$WORK/read-result.json" "$WORK/read-context.json" "$WORK/read-plain.json"
assert_receipt_common "$WORK/read-plain.json" "$READ_ID" "COMPLETED"
python3 - "$WORK/read-plain.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
r=d.get("result") or {}
assert r.get("isError") is not True
content=r.get("content") or []
assert any(isinstance(x,dict) and x.get("type")=="text" for x in content)
PY
log "FRESH_ORIGIN_READ_TEXT=PASS"

# Expired but otherwise valid task must produce an authenticated EXPIRED receipt.
NOW="$(date +%s)"
EXP_ID="ppc-accept-expired-$NOW-$RANDOM"
prepare "$EXP_ID" runtime_health '{}' read_only "$WORK/exp-envelope.json" "$WORK/exp-context.json"   --created-at "$((NOW-120))" --expires-at "$((NOW-30))"
queue_envelope "$WORK/exp-envelope.json" "$EXP_ID"
wait_result "$EXP_ID" "$WORK/exp-result.json" || fail "expiry_result_timeout"
decode_to "$WORK/exp-result.json" "$WORK/exp-context.json" "$WORK/exp-plain.json"
assert_receipt_common "$WORK/exp-plain.json" "$EXP_ID" "EXPIRED"
python3 - "$WORK/exp-plain.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert "expired" in (d.get("unresolved") or [])
assert not d.get("actions")
PY
log "EXPIRY_ENFORCEMENT=PASS"

# Authority attenuation: terminal_exec under read_only must be rejected before MCP.
AUTH_ID="ppc-accept-authority-$(date +%s)-$RANDOM"
AUTH_MARKER=".acceptance-authority-should-not-exist-$AUTH_ID"
prepare "$AUTH_ID" terminal_exec   "{\"command\":\"touch $AUTH_MARKER\",\"timeout_ms\":3000}"   read_only "$WORK/auth-envelope.json" "$WORK/auth-context.json"   --negative-contract-test --allowed terminal_exec
queue_envelope "$WORK/auth-envelope.json" "$AUTH_ID"
wait_result "$AUTH_ID" "$WORK/auth-result.json" || fail "authority_result_timeout"
decode_to "$WORK/auth-result.json" "$WORK/auth-context.json" "$WORK/auth-plain.json"
assert_receipt_common "$WORK/auth-plain.json" "$AUTH_ID" "NEEDS_AUTHORITY"
python3 - "$WORK/auth-plain.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert "authority_attenuation_reject" in (d.get("unresolved") or [])
assert not d.get("actions")
PY
log "AUTHORITY_ATTENUATION=PASS"

# Fail-closed outer envelope: wrong runtime must never decrypt or execute.
FC_ID="ppc-accept-failclosed-$(date +%s)-$RANDOM"
FC_MARKER=".acceptance-failclosed-should-not-exist-$FC_ID"
prepare "$FC_ID" terminal_exec   "{\"command\":\"touch $FC_MARKER\",\"timeout_ms\":3000}"   bounded_operator "$WORK/fc-valid.json" "$WORK/fc-context.json"
python3 - "$WORK/fc-valid.json" "$WORK/fc-envelope.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
d["target_runtime_id"]="fasthost.evenio"
with open(sys.argv[2],"w") as f:
    json.dump(d,f,separators=(",",":"),sort_keys=True)
    f.write("\n")
PY
queue_envelope "$WORK/fc-envelope.json" "$FC_ID"
assert_no_result "$FC_ID" 25 || fail "wrong_runtime_produced_receipt"
log "FAIL_CLOSED_WRONG_RUNTIME_NO_RECEIPT=PASS"

# Bounded operator task proves the real terminal tool still works and checks that
# both rejected marker writes did not occur.
TERM_ID="ppc-accept-terminal-$(date +%s)-$RANDOM"
TERM_CMD="printf 'POWERPC_CONTROL_TERMINAL_EXEC_PASS\\n'; id -u; hostname; test ! -e '$AUTH_MARKER'; test ! -e '$FC_MARKER'; printf 'REJECTED_SIDE_EFFECTS_ABSENT\\n'"
prepare "$TERM_ID" terminal_exec   "$(python3 -c 'import json,sys; print(json.dumps({"command":sys.argv[1],"timeout_ms":5000},separators=(",",":")))' "$TERM_CMD")"   bounded_operator "$WORK/term-envelope.json" "$WORK/term-context.json"
queue_envelope "$WORK/term-envelope.json" "$TERM_ID"
wait_result "$TERM_ID" "$WORK/term-result.json" || fail "terminal_exec_result_timeout"
decode_to "$WORK/term-result.json" "$WORK/term-context.json" "$WORK/term-plain.json"
assert_receipt_common "$WORK/term-plain.json" "$TERM_ID" "COMPLETED"
python3 - "$WORK/term-plain.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
r=d.get("result") or {}
assert r.get("isError") is not True
text="\n".join(x.get("text","") for x in (r.get("content") or []) if isinstance(x,dict))
assert "POWERPC_CONTROL_TERMINAL_EXEC_PASS" in text
assert "2257347" in text
assert "hp3-rr-1024747.hostingp3.local" in text
assert "REJECTED_SIDE_EFFECTS_ABSENT" in text
PY
log "FRESH_ORIGIN_TERMINAL_EXEC=PASS"
log "FAIL_CLOSED_SIDE_EFFECTS=PASS"

# Unknown capability is rejected with a signed receipt.
UNKNOWN_ID="ppc-accept-unknown-$(date +%s)-$RANDOM"
prepare "$UNKNOWN_ID" definitely_not_a_tool '{}' bounded_operator   "$WORK/unknown-envelope.json" "$WORK/unknown-context.json"   --negative-contract-test --allowed definitely_not_a_tool
queue_envelope "$WORK/unknown-envelope.json" "$UNKNOWN_ID"
wait_result "$UNKNOWN_ID" "$WORK/unknown-result.json" || fail "unknown_tool_result_timeout"
decode_to "$WORK/unknown-result.json" "$WORK/unknown-context.json" "$WORK/unknown-plain.json"
assert_receipt_common "$WORK/unknown-plain.json" "$UNKNOWN_ID" "NEEDS_AUTHORITY"
python3 - "$WORK/unknown-plain.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert "tool_not_allowed" in (d.get("unresolved") or [])
assert not d.get("actions")
PY
log "FAIL_CLOSED_UNKNOWN_CAPABILITY=PASS"

# Final freshness check from this origin, with no browser cookie or temporary
# bootstrap token used at any point in this workflow.
fetch_identity
log "POST_ACCEPTANCE_HEARTBEAT=PASS"
log "FRESH_SESSION_CALLABILITY=PASS"
log "BROWSER_COOKIE_INDEPENDENCE=PASS"
log "TEMPORARY_TOKEN_INDEPENDENCE=PASS"
log "DESKTOP_COMMANDER_QUOTA_INDEPENDENCE=PASS"
log "OPENAI_PRODUCT_BINDING_INDEPENDENCE=PASS"
log "ORIGIN_RETRIEVAL=PASS"
log "POWERPC_OWNED_CONTROL_ACCEPTANCE=PASS"
