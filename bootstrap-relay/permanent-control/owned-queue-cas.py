#!/usr/bin/env python3
"""Owner-authenticated, CAS-only encrypted operational queue on a data ref.

Separate from protected source/main and unrelated OpenAI product internals.
No source edits, private context, plaintext requests, Actions dispatch or
effectful authority. A posted envelope is not evidence of destination success.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

REPO="Christopher-Charman/open-webui"
BRANCH="runtime-queue-powerpc-darwin-org-v1"
PATH="bootstrap-relay/permanent-control/queue.json"
API=f"repos/{REPO}/contents/{PATH}"
PROTOCOL="powerpc-control-v1"
EXPECTED_TARGET="fasthost.powerpc"
TASK_ID_RE=re.compile(r"[A-Za-z0-9._-]{8,128}\Z")
MAX_QUEUE=128
MAX_BYTES=1024*1024


class QueueError(Exception):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()


def _gh(args: list[str],data: bytes | None=None) -> dict[str, Any]:
    try:
        p=subprocess.run(["gh","api",*args],
                         input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         timeout=35,check=False)
    except subprocess.TimeoutExpired as exc:
        raise QueueError("github_delivery_unknown") from exc
    if p.returncode:
        # Do not log GitHub stderr: it could contain request or auth metadata.
        raise QueueError("github_operation_unverified")
    try:
        out=json.loads(p.stdout)
    except (ValueError,UnicodeDecodeError) as exc:
        raise QueueError("github_response_invalid") from exc
    if not isinstance(out,dict):
        raise QueueError("github_response_not_object")
    return out


def read_queue() -> tuple[str,dict[str,Any]]:
    response=_gh([API+"?ref="+BRANCH])
    if response.get("path") != PATH or response.get("encoding") != "base64":
        raise QueueError("queue_blob_metadata_invalid")
    sha=response.get("sha")
    if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{40}",sha):
        raise QueueError("queue_blob_sha_unverified")
    try:
        contents=base64.b64decode(response["content"],validate=False)
        if len(contents)>MAX_BYTES:
            raise QueueError("queue_too_large")
        queue=json.loads(contents)
    except (KeyError,ValueError,UnicodeDecodeError) as exc:
        raise QueueError("queue_content_invalid") from exc
    if not isinstance(queue,dict) or queue.get("protocol")!=PROTOCOL or queue.get("version")!=1:
        raise QueueError("queue_contract_mismatch")
    tasks=queue.get("tasks")
    if not isinstance(tasks,list) or len(tasks)>MAX_QUEUE:
        raise QueueError("queue_tasks_invalid")
    if any(not isinstance(t,dict) for t in tasks):
        raise QueueError("queue_task_not_object")
    return sha,queue


def validate_encrypted_envelope(task: Any,now: int | None=None) -> str:
    if not isinstance(task,dict):
        raise QueueError("envelope_not_object")
    tid=task.get("task_id")
    if not isinstance(tid,str) or not TASK_ID_RE.fullmatch(tid):
        raise QueueError("invalid_task_id")
    if task.get("protocol")!=PROTOCOL or task.get("version")!=1:
        raise QueueError("envelope_protocol_mismatch")
    if task.get("target_runtime_id")!=EXPECTED_TARGET:
        raise QueueError("envelope_wrong_runtime")
    if any(not isinstance(task.get(k),str) or not task[k] for k in
           ("origin_ephemeral_x25519_spki_b64","nonce_b64","ciphertext_b64")):
        raise QueueError("encrypted_fields_missing")
    current=int(time.time()) if now is None else now
    created=task.get("created_at")
    expires=task.get("expires_at")
    if type(created) is not int or type(expires) is not int:
        raise QueueError("envelope_times_invalid")
    if not(current-120<=created<=current+120 and current<expires<=current+3600):
        raise QueueError("envelope_expired_or_out_of_bounds")
    # Decrypted payload remains opaque here. Runtime must independently
    # authenticate and deny any effectful request lacking write admission.
    return tid


def next_queue(current: dict[str,Any],task: dict[str,Any]) -> tuple[dict[str,Any],bool]:
    tid=validate_encrypted_envelope(task)
    tasks=current["tasks"]
    existing=[t for t in tasks if t.get("task_id")==tid]
    if existing:
        if len(existing)==1 and existing[0]==task:
            return current,False
        raise QueueError("task_id_conflict")
    if len(tasks)>=MAX_QUEUE:
        raise QueueError("queue_full")
    updated={**current,"tasks":[*tasks,task]}
    if len(canonical(updated))>MAX_BYTES:
        raise QueueError("queue_too_large")
    return updated,True


def retired_queue(current: dict[str,Any],tid: str) -> tuple[dict[str,Any],bool]:
    if not TASK_ID_RE.fullmatch(tid):
        raise QueueError("invalid_task_id")
    old=current["tasks"]
    present=sum(t.get("task_id")==tid for t in old)
    if present>1:
        raise QueueError("duplicate_task_id")
    return {**current,"tasks":[t for t in old if t.get("task_id")!=tid]},bool(present)


def cas_write(sha: str,updated: dict[str,Any],tid: str,purpose: str) -> str:
    if purpose not in ("append","retire"):
        raise QueueError("unsupported_operation")
    payload={
        "message":"control-queue: "+purpose+" task "+tid,
        "branch":BRANCH,
        "sha":sha,
        "content":base64.b64encode(canonical(updated)+b"\n").decode("ascii"),
    }
    try:
        _gh(["-X","PUT",API,"--input","-"],canonical(payload))
    except QueueError:
        # Unknown delivery MUST be reconciled from authoritative branch content.
        return "OUTCOME_UNKNOWN"
    return "WRITE_RESPONSE_OBSERVED"


def main() -> int:
    parser=argparse.ArgumentParser()
    cmd=parser.add_subparsers(dest="mode",required=True)
    app=cmd.add_parser("append")
    app.add_argument("--encrypted-task",required=True)
    retire=cmd.add_parser("retire")
    retire.add_argument("--task-id",required=True)
    retire.add_argument("--encrypted-result",required=True)
    retire.add_argument("--private-context",required=True)
    args=parser.parse_args()
    try:
        if args.mode=="append":
            taskpath=Path(args.encrypted_task)
            if taskpath.stat().st_size>MAX_BYTES:
                raise QueueError("task_file_too_large")
            task=json.loads(taskpath.read_text(encoding="utf-8"))
            tid=validate_encrypted_envelope(task)
        else:
            tid=args.task_id
            result_file=Path(args.encrypted_result)
            context_file=Path(args.private_context)
            if result_file.stat().st_size>MAX_BYTES or context_file.stat().st_size>MAX_BYTES:
                raise QueueError("receipt_or_context_too_large")
            if context_file.is_symlink():
                raise QueueError("context_symlink_denied")
            context_stat=context_file.stat()
            if context_stat.st_uid!=os.getuid() or context_stat.st_mode & 0o077:
                raise QueueError("private_context_owner_or_mode_invalid")
            # Authenticate the signed envelope and decrypt with origin-private
            # context. Never trust a caller-named plaintext receipt.
            try:
                check=subprocess.run(
                    [sys.executable,str(Path(__file__).with_name("origin-client.py")),
                     "decode","--result",str(result_file),
                     "--context",str(context_file),"--output","-"],
                    text=True,capture_output=True,timeout=20,check=False)
            except subprocess.TimeoutExpired as exc:
                raise QueueError("cryptographic_result_check_timeout") from exc
            if check.returncode!=0:
                raise QueueError("cryptographic_result_verification_failed")
            result=json.loads(check.stdout)
            if not isinstance(result,dict) or result.get("task_id")!=tid:
                raise QueueError("verified_result_task_mismatch")
            if result.get("completion_state") not in (
                "COMPLETED","FAILED","BLOCKED","EXPIRED","NEEDS_AUTHORITY"):
                raise QueueError("unrecognized_verified_receipt_state")
        sha,queue=read_queue()
        if args.mode=="append":
            updated,changed=next_queue(queue,task)
        else:
            updated,changed=retired_queue(queue,tid)
        if not changed:
            print(json.dumps({"task_id":tid,"state":"ALREADY_AT_DESIRED_STATE",
                              "branch":BRANCH},sort_keys=True))
            return 0
        response=cas_write(sha,updated,tid,args.mode)
        # Never equate GitHub API success with owner-executor completion.
        try:
            _,latest=read_queue()
        except QueueError:
            latest=None
        expected_task=[t for t in updated["tasks"] if t.get("task_id")==tid]
        seen=([t for t in latest["tasks"] if t.get("task_id")==tid]
              if latest is not None else None)
        if seen is None or seen!=expected_task:
            print(json.dumps({"task_id":tid,"state":"OUTCOME_UNKNOWN",
                              "branch":BRANCH,"write":response},sort_keys=True))
            return 2
        print(json.dumps({"task_id":tid,"state":"QUEUE_CAS_VERIFIED",
                          "branch":BRANCH,"write":response},sort_keys=True))
        return 0
    except (QueueError,ValueError,OSError) as exc:
        # Fail closed; never dump ciphertext, private context or host credentials.
        print(json.dumps({"state":"BLOCKED","reason":str(exc)},sort_keys=True))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
