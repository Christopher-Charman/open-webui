#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

ACCOUNT = Path("/home/storage/781/4477781/user")
RECEIVER_STATE = ACCOUNT / ".powerpc-control-v1"
DELEGATION_STATE = ACCOUNT / ".continuity-delegation"
RUNTIME_ID = "fasthost.powerpc"
AGENT_ID = "continuity-agent"
EXPECTED_MODEL = "qwen2.5-coder:1.5b-instruct-q4_K_M"
EXPECTED_UID = 2257347
EXPECTED_HOST = "hp3-rr-1024747.hostingp3.local"
RECEIPT_KEYS = {
    "task_id",
    "executor_identity",
    "runtime_receipt",
    "actions",
    "evidence_refs",
    "result",
    "unresolved",
    "resource_usage",
    "completion_state",
}
CAP_RE = re.compile(r"CAP-[0-9a-f]{24}")


def canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def receiver_row(task_id: str) -> dict[str, Any]:
    db = RECEIVER_STATE / "state.sqlite3"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT task_id,envelope_sha256,state,received_at,completed_at,result_path "
            "FROM tasks WHERE task_id=?",
            (task_id,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise AssertionError(f"receiver task absent: {task_id}")
    return {
        "task_id": row[0],
        "envelope_sha256": row[1],
        "state": row[2],
        "received_at": row[3],
        "completed_at": row[4],
        "result_path": row[5],
    }


def validate_outer(task_id: str) -> dict[str, Any]:
    row = receiver_row(task_id)
    assert row["state"] == "completed", (task_id, row["state"])
    assert isinstance(row["received_at"], int) and isinstance(row["completed_at"], int)
    assert row["completed_at"] >= row["received_at"]
    path = Path(row["result_path"])
    assert path.is_file(), path
    return {
        **row,
        "result_sha256": sha256_file(path),
        "result_size": path.stat().st_size,
    }


def nested_record(task_id: str) -> tuple[Path, dict[str, Any]]:
    key = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
    path = DELEGATION_STATE / "records" / f"{key}.json"
    assert path.is_file(), path
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    assert isinstance(doc.get("envelope_sha256"), str) and len(doc["envelope_sha256"]) == 64
    receipt = doc.get("receipt")
    assert isinstance(receipt, dict)
    return path, receipt


def receipt_text(result: dict[str, Any]) -> str:
    out: list[str] = []
    for item in result.get("content") or []:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            out.append(item["text"])
    return "\n".join(out)


def validate_nested(task_id: str) -> dict[str, Any]:
    path, receipt = nested_record(task_id)
    assert set(receipt) == RECEIPT_KEYS, sorted(set(receipt) ^ RECEIPT_KEYS)
    assert receipt["task_id"] == task_id
    assert receipt["completion_state"] == "COMPLETED"
    assert receipt["unresolved"] == []

    executor = receipt["executor_identity"]
    assert executor["agent_id"] == AGENT_ID
    assert executor["model_id"] == EXPECTED_MODEL
    assert executor["runtime_id"] == RUNTIME_ID

    runtime = receipt["runtime_receipt"]
    assert runtime["runtime_id"] == RUNTIME_ID
    assert runtime["uid"] == EXPECTED_UID
    assert runtime["hostname"] == EXPECTED_HOST

    actions = receipt["actions"]
    assert isinstance(actions, list) and len(actions) == 1
    assert actions[0]["capability"] == "terminal_exec"
    assert isinstance(actions[0].get("arguments_sha256"), str) and len(actions[0]["arguments_sha256"]) == 64

    evidence = receipt["evidence_refs"]
    assert isinstance(evidence, list) and len(evidence) == 1
    assert re.fullmatch(r"claim_sha256:[0-9a-f]{64}", evidence[0])

    usage = receipt["resource_usage"]
    assert usage["model_calls"] == 1
    assert usage["local_mcp_calls"] == 1
    assert usage["elapsed_ms"] > 0
    assert usage["model_ms"] > 0
    assert usage["local_mcp_ms"] > 0

    result = receipt["result"]
    assert isinstance(result, dict)
    assert result.get("isError") is False
    text = receipt_text(result)
    caps = sorted(set(CAP_RE.findall(text)))
    assert len(caps) == 1, caps
    assert str(EXPECTED_UID) in text
    assert EXPECTED_HOST in text

    st = path.stat()
    return {
        "task_id": task_id,
        "record_path": str(path),
        "record_sha256": sha256_file(path),
        "record_mtime": st.st_mtime,
        "claim_evidence": evidence[0],
        "dynamic_cap_evidence": caps[0],
        "model_id": executor["model_id"],
        "elapsed_ms": usage["elapsed_ms"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify accepted Continuity Agent delegation evidence")
    ap.add_argument("--outer-first", required=True)
    ap.add_argument("--outer-retry", required=True)
    ap.add_argument("--nested-task", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        first = validate_outer(args.outer_first)
        retry = validate_outer(args.outer_retry)
        nested = validate_nested(args.nested_task)

        # The nested durable receipt must have been produced during the first
        # outer execution and remain untouched by the later retry.  A 2-second
        # filesystem timestamp tolerance covers write/SQLite commit ordering.
        assert nested["record_mtime"] <= first["completed_at"] + 2.0
        assert nested["record_mtime"] < retry["received_at"]
        assert first["completed_at"] < retry["received_at"]

        evidence = {
            "schema": "continuity-agent-delegation-acceptance-v1",
            "acceptance": "PASS",
            "outer_first": first,
            "outer_retry": retry,
            "nested": nested,
            "invariants": {
                "outer_first_completed": True,
                "outer_retry_completed": True,
                "nested_receipt_completed": True,
                "nested_retry_without_reexecution": True,
                "model_calls": 1,
                "local_mcp_calls": 1,
                "delegation_depth": 0,
            },
        }
        evidence["evidence_fingerprint"] = "sha256:" + hashlib.sha256(canon(evidence)).hexdigest()
        if args.json:
            print(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
        else:
            print("CONTINUITY_AGENT_DELEGATION_ACCEPTANCE=PASS")
            print("OUTER_FIRST=" + args.outer_first)
            print("OUTER_RETRY=" + args.outer_retry)
            print("NESTED_TASK=" + args.nested_task)
            print("MODEL_ID=" + nested["model_id"])
            print("NESTED_RETRY_WITHOUT_REEXECUTION=PASS")
            print("EVIDENCE_FINGERPRINT=" + evidence["evidence_fingerprint"])
        return 0
    except Exception as e:
        fail = {
            "schema": "continuity-agent-delegation-acceptance-v1",
            "acceptance": "FAIL",
            "error_class": type(e).__name__,
            "error": str(e)[:1000],
        }
        if args.json:
            print(json.dumps(fail, sort_keys=True, separators=(",", ":")))
        else:
            print("CONTINUITY_AGENT_DELEGATION_ACCEPTANCE=FAIL")
            print("ERROR_CLASS=" + fail["error_class"])
            print("ERROR=" + fail["error"])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
