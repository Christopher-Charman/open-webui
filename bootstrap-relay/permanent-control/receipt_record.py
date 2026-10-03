#!/usr/bin/env python3
"""Build public-safe records for encrypted PowerPC control results."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_record(
    receipt: dict[str, Any],
    encrypted_result: dict[str, Any],
    *,
    task_id: str,
    fingerprint: str,
    request_id: str,
    tool: str,
    authority: str,
    visibility: str = "summary",
    verified_at: int | None = None,
    encrypted_result_bytes: bytes | None = None,
) -> dict[str, Any]:
    if visibility not in {"summary", "public_plaintext"}:
        raise ValueError("visibility must be summary or public_plaintext")
    if receipt.get("task_id") != task_id:
        raise ValueError("receipt task_id mismatch")
    if encrypted_result.get("task_id") != task_id:
        raise ValueError("encrypted result task_id mismatch")

    encrypted_bytes = (
        _canonical(encrypted_result)
        if encrypted_result_bytes is None
        else encrypted_result_bytes
    )
    result = receipt.get("result") or {}
    blocks = result.get("content") or []
    text_blocks = [
        item.get("text", "")
        for item in blocks
        if isinstance(item, dict)
        and item.get("type") == "text"
        and isinstance(item.get("text", ""), str)
    ]
    text_bytes = "\n".join(text_blocks).encode("utf-8")
    result_bytes = _canonical(result)
    timestamp = int(time.time()) if verified_at is None else int(verified_at)

    common = {
        "request_id": request_id,
        "target_runtime_id": "fasthost.powerpc_darwin_org",
        "legacy_protocol_runtime_id": "fasthost.powerpc",
        "task_id": task_id,
        "tool": tool,
        "authority_ceiling": authority,
        "identity_fingerprint": fingerprint,
        "verified_at": timestamp,
        "completion_state": receipt.get("completion_state"),
        "encrypted_result": {
            "carrier_path": (
                "/static/powerpc-control-v1/results/" + task_id + ".json"
            ),
            "sha256": _sha256(encrypted_bytes),
            "bytes": len(encrypted_bytes),
            "envelope": encrypted_result,
        },
    }

    if visibility == "public_plaintext":
        return {
            "schema": "chatgpt-owned-control-result-v1",
            **common,
            "result_visibility": "public_plaintext",
            "verified_receipt": receipt,
        }

    executor = receipt.get("executor_identity") or {}
    actions = receipt.get("actions") or []
    usage = receipt.get("resource_usage") or {}
    evidence_refs = receipt.get("evidence_refs") or []
    unresolved = receipt.get("unresolved") or []
    summary = {
        "task_id": task_id,
        "completion_state": receipt.get("completion_state"),
        "executor_identity": {
            key: executor[key]
            for key in ("runtime_id", "uid")
            if key in executor
        },
        "actions": [
            {
                key: action[key]
                for key in ("capability", "arguments_sha256")
                if key in action
            }
            for action in actions
            if isinstance(action, dict)
        ],
        "resource_usage": {
            "local_mcp_calls": usage.get("local_mcp_calls")
        },
        "evidence_ref_count": len(evidence_refs),
        "unresolved_count": len(unresolved),
        "result_summary": {
            "is_error": result.get("isError")
            if isinstance(result.get("isError"), bool)
            else None,
            "content_block_count": len(blocks),
            "text_bytes": len(text_bytes),
            "text_sha256": _sha256(text_bytes),
            "result_sha256": _sha256(result_bytes),
        },
        "runtime_receipt_redaction": {
            "fields": sorted((receipt.get("runtime_receipt") or {}).keys()),
            "values_omitted": True,
        },
    }
    return {
        "schema": "chatgpt-owned-control-result-summary-v1",
        **common,
        "result_visibility": "summary",
        "verified_receipt_summary": summary,
        "redactions": [
            "plaintext result content",
            "host-local runtime receipt values",
            "evidence reference values",
        ],
    }


def main() -> int:
    if len(sys.argv) != 10:
        raise SystemExit(
            "usage: receipt_record.py PLAIN ENCRYPTED OUTPUT TASK_ID FINGERPRINT "
            "REQUEST_ID TOOL AUTHORITY VISIBILITY"
        )
    plain_path, encrypted_path, output_path, task_id, fingerprint, request_id, tool, authority, visibility = sys.argv[1:]
    receipt = json.loads(Path(plain_path).read_text(encoding="utf-8"))
    encrypted_bytes = Path(encrypted_path).read_bytes()
    encrypted = json.loads(encrypted_bytes.decode("utf-8"))
    record = build_record(
        receipt,
        encrypted,
        task_id=task_id,
        fingerprint=fingerprint,
        request_id=request_id,
        tool=tool,
        authority=authority,
        visibility=visibility,
        encrypted_result_bytes=encrypted_bytes,
    )
    Path(output_path).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
