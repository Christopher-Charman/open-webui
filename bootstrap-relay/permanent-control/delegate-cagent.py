#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ACCOUNT = Path("/home/storage/781/4477781/user")
WEBAPP = ACCOUNT / "webapp"
DB = WEBAPP / "openwebui-data" / "webui.db"
STATE = ACCOUNT / ".continuity-delegation"
NODE = WEBAPP / ".local" / "node22-glibc217" / "bin" / "node"
LOCAL_MCP_HELPER = ACCOUNT / ".powerpc-control-v1" / "local-mcp-call.mjs"
OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"
OLLAMA_TAGS = "http://127.0.0.1:11434/api/tags"

RUNTIME_ID = "fasthost.powerpc"
AGENT_ID = "continuity-agent"
RECEIPT_SCHEMA = "assistant-delegation-receipt-v1"
ALLOWED_TOOLS = {"runtime_health", "read_text", "list_dir", "terminal_exec"}
TOOL_AUTHORITY = {
    "runtime_health": "read_only",
    "read_text": "read_only",
    "list_dir": "read_only",
    "terminal_exec": "bounded_operator",
}
AUTHORITY_RANK = {"read_only": 0, "bounded_operator": 1}
TASK_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class Reject(Exception):
    def __init__(self, code: str, completion_state: str):
        super().__init__(code)
        self.code = code
        self.completion_state = completion_state


def canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(canon(obj)).hexdigest()


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(canon(obj) + b"\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def runtime_receipt() -> dict[str, Any]:
    return {
        "runtime_id": RUNTIME_ID,
        "user": "csh3280350",
        "uid": os.getuid(),
        "hostname": socket.gethostname(),
        "namespace": str(ACCOUNT),
        "webapp": str(WEBAPP),
        "local_mcp": str(WEBAPP / "bin" / "local-mcp"),
    }


def make_receipt(
    task_id: str,
    *,
    model_id: str | None,
    actions: list[dict[str, Any]] | None = None,
    evidence_refs: list[Any] | None = None,
    result: Any = None,
    unresolved: list[str] | None = None,
    resource_usage: dict[str, Any] | None = None,
    completion_state: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "executor_identity": {
            "agent_id": AGENT_ID,
            "model_id": model_id,
            "runtime_id": RUNTIME_ID,
        },
        "runtime_receipt": runtime_receipt(),
        "actions": actions or [],
        "evidence_refs": evidence_refs or [],
        "result": result,
        "unresolved": unresolved or [],
        "resource_usage": resource_usage or {},
        "completion_state": completion_state,
    }


def validate_envelope(env: dict[str, Any], now: int | None = None) -> dict[str, Any]:
    now = int(time.time()) if now is None else int(now)
    required = {
        "task_id",
        "origin_runtime_identity",
        "target_agent_identity",
        "objective",
        "evidence_refs",
        "authority_ceiling",
        "allowed_capability_profile",
        "resource_budget",
        "deadline",
        "expected_result_schema",
        "return_route",
        "requested_action",
    }
    missing = sorted(required - set(env))
    if missing:
        raise Reject("missing_fields:" + ",".join(missing), "FAILED")

    task_id = env.get("task_id")
    if not isinstance(task_id, str) or not TASK_RE.fullmatch(task_id):
        raise Reject("invalid_task_id", "FAILED")

    if env.get("target_agent_identity") != AGENT_ID:
        raise Reject("wrong_target_agent", "BLOCKED")
    if env.get("expected_result_schema") != RECEIPT_SCHEMA:
        raise Reject("unsupported_result_schema", "BLOCKED")
    if not isinstance(env.get("origin_runtime_identity"), str) or not env["origin_runtime_identity"][:256]:
        raise Reject("invalid_origin_identity", "FAILED")
    if not isinstance(env.get("objective"), str) or not (1 <= len(env["objective"]) <= 4000):
        raise Reject("invalid_objective", "FAILED")
    if not isinstance(env.get("evidence_refs"), list):
        raise Reject("invalid_evidence_refs", "FAILED")
    if not isinstance(env.get("return_route"), str) or not env["return_route"][:512]:
        raise Reject("invalid_return_route", "FAILED")

    deadline = env.get("deadline")
    if not isinstance(deadline, int):
        raise Reject("invalid_deadline", "FAILED")
    if deadline <= now:
        raise Reject("expired", "EXPIRED")
    if deadline > now + 3600:
        raise Reject("deadline_exceeds_bound", "BLOCKED")

    depth = env.get("delegation_depth", 0)
    if depth != 0:
        raise Reject("delegation_depth_exceeded", "BLOCKED")

    authority = env.get("authority_ceiling")
    if authority not in AUTHORITY_RANK:
        raise Reject("unsupported_authority", "NEEDS_AUTHORITY")

    profile = env.get("allowed_capability_profile")
    if not isinstance(profile, list) or not all(isinstance(x, str) for x in profile):
        raise Reject("invalid_capability_profile", "FAILED")

    action = env.get("requested_action")
    if not isinstance(action, dict):
        raise Reject("invalid_requested_action", "FAILED")
    tool = action.get("tool")
    arguments = action.get("arguments", {})
    if tool not in ALLOWED_TOOLS:
        raise Reject("tool_not_allowed", "NEEDS_AUTHORITY")
    if tool not in profile:
        raise Reject("capability_not_delegated", "NEEDS_AUTHORITY")
    if AUTHORITY_RANK[authority] < AUTHORITY_RANK[TOOL_AUTHORITY[tool]]:
        raise Reject("authority_attenuation_reject", "NEEDS_AUTHORITY")
    if not isinstance(arguments, dict):
        raise Reject("invalid_tool_arguments", "FAILED")

    if tool == "terminal_exec":
        command = arguments.get("command")
        timeout_ms = arguments.get("timeout_ms", 10000)
        if not isinstance(command, str) or not (1 <= len(command) <= 8192):
            raise Reject("invalid_terminal_command", "FAILED")
        if not isinstance(timeout_ms, int) or not (100 <= timeout_ms <= 30000):
            raise Reject("invalid_terminal_timeout", "FAILED")

    budget = env.get("resource_budget")
    if not isinstance(budget, dict):
        raise Reject("invalid_resource_budget", "FAILED")
    model_calls = budget.get("model_calls", 1)
    local_mcp_calls = budget.get("local_mcp_calls", budget.get("terminal_calls", 1))
    wall_seconds = budget.get("wall_seconds", 120)
    if not isinstance(model_calls, int) or not (1 <= model_calls <= 1):
        raise Reject("model_call_budget_exceeded", "BLOCKED")
    if not isinstance(local_mcp_calls, int) or not (1 <= local_mcp_calls <= 1):
        raise Reject("local_mcp_budget_exceeded", "BLOCKED")
    if not isinstance(wall_seconds, int) or not (5 <= wall_seconds <= 300):
        raise Reject("invalid_wall_budget", "BLOCKED")

    return {
        "task_id": task_id,
        "tool": tool,
        "arguments": arguments,
        "authority": authority,
        "wall_seconds": wall_seconds,
        "deadline": deadline,
    }


def resolve_claim_model() -> str:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT base_model_id,is_active FROM model WHERE id=?",
            (AGENT_ID,),
        ).fetchone()
    finally:
        con.close()
    if not row or not row[1]:
        raise Reject("continuity_agent_unavailable", "BLOCKED")
    model_id = row[0]
    if not isinstance(model_id, str) or not model_id:
        raise Reject("continuity_agent_base_missing", "BLOCKED")

    req = urllib.request.Request(OLLAMA_TAGS, headers={"User-Agent": "continuity-delegation-v1/1"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            tags = json.loads(r.read())
    except Exception as e:
        raise Reject("ollama_unavailable:" + type(e).__name__, "BLOCKED")
    names = {m.get("name") for m in tags.get("models", []) if isinstance(m, dict)}
    if model_id not in names:
        raise Reject("continuity_agent_base_unavailable", "BLOCKED")
    return model_id


def claim_task(env: dict[str, Any], validated: dict[str, Any], model_id: str, timeout: float) -> tuple[dict[str, Any], int]:
    claim_input = {
        "task_id": validated["task_id"],
        "objective": env["objective"][:800],
        "capability": validated["tool"],
        "authority_ceiling": validated["authority"],
        "allowed_capability_profile": env["allowed_capability_profile"],
        "delegation_depth": env.get("delegation_depth", 0),
    }
    system = (
        "You are the Continuity Agent admission node. This is CLAIM/DECLINE only; "
        "do not execute the task and do not invent evidence. Return one JSON object "
        'with exactly {"task_id":string,"decision":"CLAIM"|"DECLINE","capability":string}. '
        "CLAIM only when the requested capability is explicitly allowed and the objective "
        "is consistent with that capability."
    )
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(claim_input, separators=(",", ":"), sort_keys=True)},
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_ctx": 1024,
            "num_predict": 64,
        },
        "keep_alive": "5m",
    }
    req = urllib.request.Request(
        OLLAMA_CHAT,
        data=canon(payload),
        headers={"Content-Type": "application/json", "User-Agent": "continuity-delegation-v1/1"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=max(1.0, timeout)) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise Reject("claim_http_" + str(e.code), "BLOCKED")
    except Exception as e:
        raise Reject("claim_failed:" + type(e).__name__, "BLOCKED")
    elapsed_ms = int((time.monotonic() - started) * 1000)
    content = ((out.get("message") or {}).get("content") or "").strip()
    try:
        claim = json.loads(content)
    except Exception:
        raise Reject("invalid_claim_json", "BLOCKED")
    if set(claim) != {"task_id", "decision", "capability"}:
        raise Reject("invalid_claim_shape", "BLOCKED")
    if claim.get("task_id") != validated["task_id"] or claim.get("capability") != validated["tool"]:
        raise Reject("claim_binding_mismatch", "BLOCKED")
    if claim.get("decision") not in {"CLAIM", "DECLINE"}:
        raise Reject("invalid_claim_decision", "BLOCKED")
    return claim, elapsed_ms


def call_local_mcp(tool: str, arguments: dict[str, Any], timeout: float) -> tuple[dict[str, Any], int]:
    if not NODE.is_file() or not LOCAL_MCP_HELPER.is_file():
        raise Reject("local_mcp_helper_unavailable", "FAILED")
    started = time.monotonic()
    try:
        p = subprocess.run(
            [str(NODE), str(LOCAL_MCP_HELPER)],
            input=canon({"tool": tool, "arguments": arguments}),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(WEBAPP),
            env={**os.environ, "HOME": str(ACCOUNT)},
            timeout=max(1.0, timeout),
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise Reject("local_mcp_timeout", "FAILED")
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if p.returncode != 0:
        raise Reject("local_mcp_process_failed", "FAILED")
    try:
        result = json.loads(p.stdout.decode("utf-8"))
    except Exception:
        raise Reject("invalid_local_mcp_result", "FAILED")
    if not isinstance(result, dict):
        raise Reject("invalid_local_mcp_result", "FAILED")
    return result, elapsed_ms


def state_paths(task_id: str) -> tuple[Path, Path]:
    key = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
    return STATE / "records" / (key + ".json"), STATE / "delegation.lock"


def load_record(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def run(env: dict[str, Any]) -> dict[str, Any]:
    task_id = env.get("task_id") if isinstance(env.get("task_id"), str) else "INVALID"
    envelope_sha = sha256_obj(env)
    STATE.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    record_path, lock_path = state_paths(task_id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+") as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        record = load_record(record_path)
        if record is not None:
            if record.get("envelope_sha256") == envelope_sha:
                return record["receipt"]
            return make_receipt(
                task_id,
                model_id=None,
                unresolved=["task_id_conflict"],
                completion_state="FAILED",
            )

        started = time.monotonic()
        model_id: str | None = None
        try:
            validated = validate_envelope(env)
            remaining = min(
                float(validated["wall_seconds"]),
                float(validated["deadline"] - int(time.time())),
            )
            if remaining <= 0:
                raise Reject("expired", "EXPIRED")

            model_id = resolve_claim_model()
            claim, model_ms = claim_task(env, validated, model_id, min(30.0, remaining))
            claim_digest = sha256_obj(claim)
            if claim["decision"] != "CLAIM":
                receipt = make_receipt(
                    task_id,
                    model_id=model_id,
                    evidence_refs=["claim_sha256:" + claim_digest],
                    unresolved=["agent_declined"],
                    resource_usage={"model_calls": 1, "local_mcp_calls": 0, "model_ms": model_ms},
                    completion_state="BLOCKED",
                )
            else:
                elapsed = time.monotonic() - started
                remaining = min(
                    float(validated["wall_seconds"]) - elapsed,
                    float(validated["deadline"] - int(time.time())),
                )
                if remaining <= 0:
                    raise Reject("expired_after_claim", "EXPIRED")
                result, mcp_ms = call_local_mcp(
                    validated["tool"],
                    validated["arguments"],
                    min(30.0, remaining),
                )
                state = "FAILED" if result.get("isError") is True else "COMPLETED"
                unresolved = ["local_mcp_is_error"] if state == "FAILED" else []
                receipt = make_receipt(
                    task_id,
                    model_id=model_id,
                    actions=[{
                        "capability": validated["tool"],
                        "arguments_sha256": sha256_obj(validated["arguments"]),
                    }],
                    evidence_refs=["claim_sha256:" + claim_digest],
                    result=result,
                    unresolved=unresolved,
                    resource_usage={
                        "model_calls": 1,
                        "local_mcp_calls": 1,
                        "model_ms": model_ms,
                        "local_mcp_ms": mcp_ms,
                        "elapsed_ms": int((time.monotonic() - started) * 1000),
                    },
                    completion_state=state,
                )
        except Reject as e:
            receipt = make_receipt(
                task_id,
                model_id=model_id,
                unresolved=[e.code],
                resource_usage={"elapsed_ms": int((time.monotonic() - started) * 1000)},
                completion_state=e.completion_state,
            )
        except Exception as e:
            receipt = make_receipt(
                task_id,
                model_id=model_id,
                unresolved=[type(e).__name__ + ":" + str(e)[:500]],
                resource_usage={"elapsed_ms": int((time.monotonic() - started) * 1000)},
                completion_state="FAILED",
            )

        atomic_json(record_path, {"envelope_sha256": envelope_sha, "receipt": receipt})
        return receipt


def self_test() -> int:
    now = 2_000_000_000
    base = {
        "task_id": "selftest-1",
        "origin_runtime_identity": "test-origin",
        "target_agent_identity": AGENT_ID,
        "objective": "List the bounded runtime directory.",
        "evidence_refs": [],
        "authority_ceiling": "read_only",
        "allowed_capability_profile": ["list_dir"],
        "resource_budget": {"model_calls": 1, "local_mcp_calls": 1, "wall_seconds": 30},
        "deadline": now + 60,
        "expected_result_schema": RECEIPT_SCHEMA,
        "return_route": "stdout",
        "requested_action": {"tool": "list_dir", "arguments": {"path": "."}},
        "delegation_depth": 0,
    }
    assert validate_envelope(base, now)["tool"] == "list_dir"

    expired = dict(base, task_id="selftest-expired", deadline=now - 1)
    try:
        validate_envelope(expired, now)
        raise AssertionError("expired accepted")
    except Reject as e:
        assert e.completion_state == "EXPIRED"

    authority = dict(base, task_id="selftest-authority", requested_action={
        "tool": "terminal_exec", "arguments": {"command": "true", "timeout_ms": 1000}
    }, allowed_capability_profile=["terminal_exec"])
    try:
        validate_envelope(authority, now)
        raise AssertionError("authority attenuation accepted")
    except Reject as e:
        assert e.completion_state == "NEEDS_AUTHORITY"

    depth = dict(base, task_id="selftest-depth", delegation_depth=1)
    try:
        validate_envelope(depth, now)
        raise AssertionError("delegation recursion accepted")
    except Reject as e:
        assert e.completion_state == "BLOCKED"

    unknown = dict(base, task_id="selftest-tool", requested_action={"tool": "not_a_tool", "arguments": {}},
                   allowed_capability_profile=["not_a_tool"])
    try:
        validate_envelope(unknown, now)
        raise AssertionError("unknown tool accepted")
    except Reject as e:
        assert e.completion_state == "NEEDS_AUTHORITY"

    print("DELEGATE_CAGENT_SELFTEST=PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="-", help="Envelope JSON file or - for stdin")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    raw = sys.stdin.buffer.read() if args.input == "-" else Path(args.input).read_bytes()
    try:
        env = json.loads(raw.decode("utf-8"))
        if not isinstance(env, dict):
            raise ValueError("envelope must be object")
    except Exception as e:
        receipt = make_receipt(
            "INVALID",
            model_id=None,
            unresolved=["invalid_json:" + type(e).__name__],
            completion_state="FAILED",
        )
        sys.stdout.buffer.write(canon(receipt) + b"\n")
        return 2
    receipt = run(env)
    sys.stdout.buffer.write(canon(receipt) + b"\n")
    return 0 if receipt.get("completion_state") == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
