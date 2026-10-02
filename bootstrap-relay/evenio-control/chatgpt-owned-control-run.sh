#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
DIR="$ROOT/bootstrap-relay/evenio-control"
REQUEST="$DIR/chatgpt-request.json"
QUEUE="$DIR/queue.json"
CLIENT="$DIR/origin-client.py"
IDENTITY_URL="${EVENIO_CHATGPT_IDENTITY_URL:-https://evenio.online/evenio-control-v1/identity.json}"
RESULT_BASE="${EVENIO_CHATGPT_RESULT_BASE:-https://evenio.online/evenio-control-v1/results}"
WORK="$(mktemp -d)"
IDENTITY="$WORK/identity.json"
ENVELOPE="$WORK/envelope.json"
CONTEXT="$WORK/context.json"
ENCRYPTED_RESULT="$WORK/result.json"
PLAIN_RESULT="$WORK/plain.json"
TASK_QUEUED=0

git config user.name "ChatGPT Evenio Owned Control"
git config user.email "61332783+Christopher-Charman@users.noreply.github.com"

cleanup_task_only() {
  [ "$TASK_QUEUED" = "1" ] || return 0
  local attempt
  for attempt in 1 2 3 4 5; do
    git fetch origin main >/dev/null 2>&1 || continue
    git reset --hard origin/main >/dev/null 2>&1 || continue
    python3 - "$QUEUE" "$TASK_ID" <<'PY'
import json,sys
path,tid=sys.argv[1:3]
q=json.load(open(path,encoding="utf-8"))
tasks=q.get("tasks")
assert q.get("protocol")=="evenio-control-v1" and q.get("version")==1 and isinstance(tasks,list)
q["tasks"]=[x for x in tasks if not (isinstance(x,dict) and x.get("task_id")==tid)]
with open(path,"w",encoding="utf-8") as f:
    json.dump(q,f,separators=(",",":"),sort_keys=True); f.write("\n")
PY
    if git diff --quiet -- "$QUEUE"; then TASK_QUEUED=0; return 0; fi
    git add "$QUEUE"
    git commit -m "control: retire ChatGPT owned-control task $TASK_ID" >/dev/null 2>&1 || continue
    if git push origin HEAD:main >/dev/null 2>&1; then TASK_QUEUED=0; return 0; fi
  done
  return 1
}

on_exit() {
  rc=$?
  set +e
  cleanup_task_only
  rm -rf "$WORK"
  exit "$rc"
}
trap on_exit EXIT INT TERM

python3 - "$REQUEST" <<'PY'
import json,re,sys
p=sys.argv[1]
d=json.load(open(p,encoding="utf-8"))
assert d.get("schema")=="chatgpt-owned-control-request-v1"
rid=d.get("request_id")
assert isinstance(rid,str) and re.fullmatch(r"[A-Za-z0-9._-]{8,80}",rid)
assert d.get("target_runtime_id")=="fasthost.evenio"
tool=d.get("tool")
assert tool in {"runtime_health","control_state","runtime_audit"}
args=d.get("arguments")
assert isinstance(args,dict)
auth=d.get("authority_ceiling","read_only")
assert auth=="read_only"
ttl=d.get("ttl",300)
assert isinstance(ttl,int) and 30 <= ttl <= 600
PY

REQUEST_ID="$(python3 -c 'import json; print(json.load(open("'"$REQUEST"'"))["request_id"])')"
TOOL="$(python3 -c 'import json; print(json.load(open("'"$REQUEST"'"))["tool"])')"
AUTHORITY="$(python3 -c 'import json; print(json.load(open("'"$REQUEST"'")).get("authority_ceiling","read_only"))')"
TTL="$(python3 -c 'import json; print(json.load(open("'"$REQUEST"'")).get("ttl",300))')"
ARGS="$(python3 -c 'import json; print(json.dumps(json.load(open("'"$REQUEST"'"))["arguments"],separators=(",",":")))' )"
TASK_ID="chatgpt-$REQUEST_ID"
RESULT_REL="bootstrap-relay/evenio-control/chatgpt-results/$REQUEST_ID.json"
RESULT_PATH="$ROOT/$RESULT_REL"

if [ -f "$RESULT_PATH" ]; then
  echo "CHATGPT_OWNED_CONTROL_RESULT=ALREADY_PRESENT"
  echo "request_id=$REQUEST_ID"
  exit 0
fi

curl -fsSL --connect-timeout 10 --max-time 30 "$IDENTITY_URL?t=$(date +%s%N)" -o "$IDENTITY"

PREP_OUT="$(python3 "$CLIENT" prepare   --identity "$IDENTITY"   --task-id "$TASK_ID"   --tool "$TOOL"   --arguments "$ARGS"   --authority "$AUTHORITY"   --ttl "$TTL"   --output "$ENVELOPE"   --context "$CONTEXT")"
FP="$(printf '%s\n' "$PREP_OUT" | sed -n 's/^IDENTITY_FINGERPRINT=//p' | tail -n1)"
[ -n "$FP" ] || { echo "identity verification failed" >&2; exit 1; }
echo "::add-mask::$FP"

for attempt in 1 2 3 4 5; do
  git fetch origin main >/dev/null 2>&1
  git reset --hard origin/main >/dev/null 2>&1
  if [ -f "$RESULT_PATH" ]; then
    echo "CHATGPT_OWNED_CONTROL_RESULT=ALREADY_PRESENT"
    exit 0
  fi
  python3 - "$ENVELOPE" "$QUEUE" <<'PY'
import json,sys
ep,qp=sys.argv[1:3]
task=json.load(open(ep,encoding="utf-8"))
q=json.load(open(qp,encoding="utf-8"))
assert q.get("protocol")=="evenio-control-v1" and q.get("version")==1
tasks=q.get("tasks"); assert isinstance(tasks,list)
tid=task["task_id"]
same=[x for x in tasks if isinstance(x,dict) and x.get("task_id")==tid]
if same:
    if len(same)==1 and same[0]==task: raise SystemExit(0)
    raise SystemExit("task_id conflict")
assert len(tasks)<128
tasks.append(task)
with open(qp,"w",encoding="utf-8") as f:
    json.dump(q,f,separators=(",",":"),sort_keys=True); f.write("\n")
PY
  if git diff --quiet -- "$QUEUE"; then TASK_QUEUED=1; break; fi
  git add "$QUEUE"
  git commit -m "control: ChatGPT owned-control task $TASK_ID" >/dev/null
  if git push origin HEAD:main >/dev/null 2>&1; then TASK_QUEUED=1; break; fi
done
[ "$TASK_QUEUED" = "1" ] || { echo "queue append conflict" >&2; exit 1; }

deadline=$((SECONDS + TTL))
while (( SECONDS < deadline )); do
  if curl -fsSL --connect-timeout 8 --max-time 20       "$RESULT_BASE/$TASK_ID.json?t=$(date +%s%N)" -o "$ENCRYPTED_RESULT" 2>/dev/null; then
    if python3 - "$ENCRYPTED_RESULT" "$TASK_ID" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d.get("protocol")=="evenio-control-v1"
assert d.get("task_id")==sys.argv[2]
assert d.get("kind")=="result"
PY
    then break; fi
  fi
  sleep 2
done
[ -s "$ENCRYPTED_RESULT" ] || { echo "receipt timeout" >&2; exit 1; }

python3 "$CLIENT" decode --result "$ENCRYPTED_RESULT" --context "$CONTEXT" --output "$PLAIN_RESULT" >/dev/null

python3 - "$REQUEST" "$PLAIN_RESULT" "$WORK/adapter-result.json" "$TASK_ID" "$FP" <<'PY'
import json,sys,time
req_path,plain_path,out_path,task_id,fp=sys.argv[1:6]
req=json.load(open(req_path,encoding="utf-8"))
receipt=json.load(open(plain_path,encoding="utf-8"))
assert receipt.get("task_id")==task_id
out={
  "schema":"chatgpt-owned-control-result-v1",
  "request_id":req["request_id"],
  "target_runtime_id":"fasthost.evenio",
  "task_id":task_id,
  "tool":req["tool"],
  "authority_ceiling":req.get("authority_ceiling","read_only"),
  "identity_fingerprint":fp,
  "verified_at":int(time.time()),
  "completion_state":receipt.get("completion_state"),
  "verified_receipt":receipt,
}
with open(out_path,"w",encoding="utf-8") as f:
    json.dump(out,f,indent=2,sort_keys=True); f.write("\n")
PY

for attempt in 1 2 3 4 5; do
  git fetch origin main >/dev/null 2>&1 || continue
  git reset --hard origin/main >/dev/null 2>&1 || continue
  mkdir -p "$(dirname "$RESULT_PATH")"
  cp "$WORK/adapter-result.json" "$RESULT_PATH"
  python3 - "$QUEUE" "$TASK_ID" <<'PY'
import json,sys
path,tid=sys.argv[1:3]
q=json.load(open(path,encoding="utf-8"))
tasks=q.get("tasks"); assert isinstance(tasks,list)
q["tasks"]=[x for x in tasks if not (isinstance(x,dict) and x.get("task_id")==tid)]
with open(path,"w",encoding="utf-8") as f:
    json.dump(q,f,separators=(",",":"),sort_keys=True); f.write("\n")
PY
  git add "$QUEUE" "$RESULT_REL"
  git commit -m "control: verified ChatGPT owned-control result $REQUEST_ID" >/dev/null
  if git push origin HEAD:main >/dev/null 2>&1; then
    TASK_QUEUED=0
    echo "CHATGPT_OWNED_CONTROL_RESULT=VERIFIED"
    echo "request_id=$REQUEST_ID"
    echo "task_id=$TASK_ID"
    echo "result_path=$RESULT_REL"
    exit 0
  fi
done

echo "result publication conflict" >&2
exit 1
