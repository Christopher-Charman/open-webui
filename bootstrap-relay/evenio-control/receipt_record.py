#!/usr/bin/env python3
"""Build a public-safe summary record for encrypted Evenio control results."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if len(sys.argv) != 8:
        raise SystemExit("usage: receipt_record.py PLAIN ENCRYPTED OUTPUT TASK_ID FINGERPRINT REQUEST_ID TOOL AUTHORITY")
    plain_path, encrypted_path, output_path, task_id, fingerprint, request_id, tool, authority = sys.argv[1:]
    receipt = json.loads(Path(plain_path).read_text(encoding="utf-8"))
    encrypted_bytes = Path(encrypted_path).read_bytes()
    encrypted = json.loads(encrypted_bytes.decode("utf-8"))
    if receipt.get("task_id") != task_id or encrypted.get("task_id") != task_id:
        raise ValueError("result task_id mismatch")
    result = receipt.get("result") or {}
    actions = receipt.get("actions") or []
    unresolved = receipt.get("unresolved") or []
    evidence_refs = receipt.get("evidence_refs") or []
    runtime_receipt = receipt.get("runtime_receipt") or {}
    executor = receipt.get("executor_identity") or {}
    record = {
        "schema": "chatgpt-owned-control-result-summary-v1",
        "request_id": request_id,
        "target_runtime_id": "fasthost.evenio",
        "task_id": task_id,
        "tool": tool,
        "authority_ceiling": authority,
        "identity_fingerprint": fingerprint,
        "verified_at": int(time.time()),
        "completion_state": receipt.get("completion_state"),
        "encrypted_result": {
            "sha256": sha256(encrypted_bytes),
            "bytes": len(encrypted_bytes),
            "envelope": encrypted,
        },
        "verified_receipt_summary": {
            "executor_identity": {"runtime_id": executor.get("runtime_id")} if executor.get("runtime_id") else {},
            "actions": [
                {k: a[k] for k in ("capability", "arguments_sha256") if k in a}
                for a in actions if isinstance(a, dict)
            ],
            "evidence_ref_count": len(evidence_refs),
            "unresolved_count": len(unresolved),
            "result_sha256": sha256(canonical(result)),
            "runtime_receipt_redaction": {
                "fields": sorted(runtime_receipt.keys()),
                "values_omitted": True,
            },
        },
        "redactions": [
            "plaintext result content",
            "executor hostname/user/uid",
            "host-local runtime receipt values",
            "evidence reference values",
        ],
    }
    Path(output_path).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
