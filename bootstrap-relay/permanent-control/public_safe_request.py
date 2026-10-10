#!/usr/bin/env python3
"""Strict public-safe ChatGPT Actions ingress request contract.

This subprocess validates a *request*, not a destination mutation authority.
Effectful control belongs to independently admitted user-owned private routes.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA = "chatgpt-owned-control-request-v1"
TARGET = "fasthost.powerpc_darwin_org"
ALLOWED_TOOLS = frozenset({"runtime_health", "read_text", "list_dir"})
FIELDS = frozenset({
    "schema", "request_id", "target_runtime_id", "tool", "arguments",
    "authority_ceiling", "ttl", "result_visibility",
})
_ID = re.compile(r"[A-Za-z0-9._-]{8,80}\Z")


def validate_public_safe_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("request_not_object")
    if set(value) - FIELDS:
        raise ValueError("unrecognized_request_fields")
    if value.get("schema") != SCHEMA:
        raise ValueError("request_schema_mismatch")
    request_id = value.get("request_id")
    if not isinstance(request_id, str) or not _ID.fullmatch(request_id):
        raise ValueError("invalid_request_id")
    if value.get("target_runtime_id") != TARGET:
        raise ValueError("wrong_owned_runtime")
    if value.get("tool") not in ALLOWED_TOOLS:
        raise ValueError("public_safe_tool_not_permitted")
    if not isinstance(value.get("arguments"), dict):
        raise ValueError("arguments_not_object")
    if value.get("authority_ceiling", "read_only") != "read_only":
        raise ValueError("public_safe_authority_must_be_read_only")
    ttl = value.get("ttl", 300)
    if type(ttl) is not int or not (30 <= ttl <= 600):
        raise ValueError("ttl_out_of_bounds")
    if value.get("result_visibility", "summary") != "summary":
        raise ValueError("public_safe_result_must_be_summary")
    return {
        "request_id": request_id,
        "target_runtime_id": TARGET,
        "tool": value["tool"],
        "authority_ceiling": "read_only",
        "result_visibility": "summary",
        "ttl": ttl,
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: public_safe_request.py request.json")
    path = Path(sys.argv[1])
    if path.stat().st_size > 65536:
        raise ValueError("request_too_large")
    with path.open("r", encoding="utf-8") as f:
        validate_public_safe_request(json.load(f))
    print("PUBLIC_SAFE_ADMISSION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
