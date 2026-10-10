#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ACCOUNT = Path(os.environ.get("PPC_ACCOUNT", str(Path.home())))
WEBAPP = ACCOUNT / "webapp"
STATE = ACCOUNT / ".continuity-delegation"
NODE = WEBAPP / ".local" / "node22-glibc217" / "bin" / "node"
LOCAL_MCP_HELPER = ACCOUNT / ".powerpc-control-v1" / "local-mcp-call.mjs"
OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"
OLLAMA_TAGS = "http://127.0.0.1:11434/api/tags"
LEDGER_SRC = WEBAPP / "concurrency-ledger" / "current" / "src"
LEDGER_CLIENT = WEBAPP / "bin" / "concurrency-ledger-cagent-call"
LEDGER_ACTOR_ID = "actor:continuity-agent"
LEDGER_SURFACE_ID = "openwebui:continuity-agent"
LEDGER_PROJECT_ID = "concurrency.orchestration"
LEDGER_ROLE_ASSIGNMENT_ID = "assignment:continuity-agent:concurrency.orchestration:read"
LEDGER_FRONTIER_LIMIT = 10

RUNTIME_ID = "fasthost.powerpc"
AGENT_ID = "continuity-agent"
CLAIM_MODEL_ID = "qwen2.5-coder:1.5b-instruct-q4_K_M"
CLAIM_MODEL_SEED = 42
RECEIPT_SCHEMA = "assistant-delegation-receipt-v1"
ALLOWED_TOOLS = {"runtime_health", "read_text", "list_dir", "terminal_exec"}
TOOL_AUTHORITY = {
    "runtime_health": "read_only",
    "read_text": "read_only",
    "list_dir": "read_only",
    "terminal_exec": "bounded_operator",
}
INTENT_CLASS_BY_TOOL = {
    "runtime_health": "runtime_health",
    "read_text": "filesystem_read",
    "list_dir": "filesystem_read",
    "terminal_exec": "bounded_operator_command",
}
SUPPORTED_INTENT_CLASSES = frozenset(INTENT_CLASS_BY_TOOL.values())
# This receiver has verified session/frontier READ rights, not destination
# mutation admission. Effect-capable tools must never use session visibility or
# a model-generated CLAIM to infer a task/claim/run/lease/fence/CAS grant.
EFFECT_CAPABLE_TOOLS = frozenset({"terminal_exec"})
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
        "user": os.environ.get("USER", "unknown"),
        "uid": os.getuid(),
        "hostname": socket.gethostname(),
        "namespace": str(ACCOUNT),
        "webapp": str(WEBAPP),
        "local_mcp": str(WEBAPP / "bin" / "local-mcp"),
    }


def _ledger_task_key(task_id: str) -> str:
    return hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:24]


def _ledger_adapter(role_assignment_id: str | None = None):
    if not LEDGER_SRC.is_dir() or not LEDGER_CLIENT.is_file():
        raise Reject("ledger_adapter_unavailable", "BLOCKED")
    source = str(LEDGER_SRC)
    if source not in sys.path:
        sys.path.insert(0, source)
    try:
        from concurrency_ledger.c_agent_adapter import (
            CAgentLedgerBinding,
            CAgentLedgerRequestAdapter,
        )
    except Exception as exc:
        raise Reject(
            "ledger_adapter_import_failed:" + type(exc).__name__,
            "BLOCKED",
        ) from exc
    try:
        return CAgentLedgerRequestAdapter(
            CAgentLedgerBinding(
                actor_id=LEDGER_ACTOR_ID,
                role_assignment_id=role_assignment_id,
                surface_id=LEDGER_SURFACE_ID,
                project_id=LEDGER_PROJECT_ID,
            )
        )
    except Exception as exc:
        raise Reject(
            "ledger_adapter_binding_failed:" + type(exc).__name__,
            "BLOCKED",
        ) from exc


def _ledger_call(request: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
    if not LEDGER_CLIENT.is_file() or not os.access(LEDGER_CLIENT, os.X_OK):
        raise Reject("ledger_client_unavailable", "BLOCKED")
    timeout_value = float(timeout)
    if timeout_value <= 0:
        raise Reject("ledger_call_budget_exhausted", "BLOCKED")
    try:
        proc = subprocess.run(
            [str(LEDGER_CLIENT), "-"],
            input=canon(request),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(WEBAPP),
            env={**os.environ, "HOME": str(ACCOUNT)},
            timeout=max(0.1, min(timeout_value, 20.0)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise Reject("ledger_call_timeout", "BLOCKED") from exc
    except Exception as exc:
        raise Reject(
            "ledger_call_failed:" + type(exc).__name__,
            "BLOCKED",
        ) from exc
    if proc.returncode != 0:
        raise Reject("ledger_call_rejected", "BLOCKED")
    try:
        result = json.loads(proc.stdout.decode("utf-8"))
    except Exception as exc:
        raise Reject("ledger_result_invalid", "BLOCKED") from exc
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise Reject("ledger_result_rejected", "BLOCKED")
    return result


def open_ledger_session(
    task_id: str,
    *,
    timeout: float = 30.0,
) -> tuple[str, str]:
    """Open and heartbeat a role-free C-Agent coordination session.

    The two ledger calls share one total timeout budget. This establishes only
    authenticated session provenance. It grants no role, project-read,
    task-owner, claim, run, lease, or mutation authority.
    """
    adapter = _ledger_adapter()
    key = _ledger_task_key(task_id)
    correlation_id = "cagent-delegation:" + key
    started = time.monotonic()

    def remaining_timeout() -> float:
        remaining = float(timeout) - (time.monotonic() - started)
        if remaining <= 0:
            raise Reject("ledger_session_budget_exhausted", "BLOCKED")
        return remaining

    opened = _ledger_call(
        adapter.session_open(
            request_id="cagent-session-open-" + key,
            idempotency_key="cagent-session-open-" + key,
            now=datetime.now(timezone.utc),
            correlation_id=correlation_id,
        ),
        timeout=remaining_timeout(),
    )
    session_id = (opened.get("result") or {}).get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise Reject("ledger_session_id_missing", "BLOCKED")

    heartbeat = _ledger_call(
        adapter.session_heartbeat(
            session_id=session_id,
            request_id="cagent-session-heartbeat-" + key,
            idempotency_key="cagent-session-heartbeat-" + key,
            now=datetime.now(timezone.utc),
            correlation_id=correlation_id,
            causation_id="cagent-session-open-" + key,
        ),
        timeout=remaining_timeout(),
    )
    heartbeat_at = (heartbeat.get("result") or {}).get("heartbeat_at")
    if not isinstance(heartbeat_at, str) or not heartbeat_at:
        raise Reject("ledger_session_heartbeat_missing", "BLOCKED")
    return session_id, heartbeat_at


def read_ledger_frontier(
    task_id: str,
    session_id: str,
    *,
    timeout: float = 15.0,
) -> tuple[dict[str, Any], str]:
    """Read and validate the bounded project coordination frontier.

    This consumes only the already-authorized LEDGER_PROJECT_READ projection.
    The summary is evidence/context only and never establishes task ownership,
    claim admission, run/lease authority, or destination mutation authority.
    """
    adapter = _ledger_adapter(LEDGER_ROLE_ASSIGNMENT_ID)
    key = _ledger_task_key(task_id)
    correlation_id = "cagent-delegation:" + key
    frontier_response = _ledger_call(
        adapter.frontier(
            session_id=session_id,
            request_id="cagent-frontier-" + key,
            idempotency_key="cagent-frontier-" + key,
            now=datetime.now(timezone.utc),
            limit=LEDGER_FRONTIER_LIMIT,
            correlation_id=correlation_id,
            causation_id="cagent-session-heartbeat-" + key,
        ),
        timeout=timeout,
    )
    frontier = frontier_response.get("result")
    if not isinstance(frontier, dict):
        raise Reject("ledger_frontier_missing", "BLOCKED")
    if frontier.get("project_id") != LEDGER_PROJECT_ID:
        raise Reject("ledger_frontier_project_mismatch", "BLOCKED")
    filters = frontier.get("filters")
    if not isinstance(filters, dict) or filters.get("limit") != LEDGER_FRONTIER_LIMIT:
        raise Reject("ledger_frontier_filter_mismatch", "BLOCKED")
    invariants = frontier.get("invariants")
    if not isinstance(invariants, list):
        raise Reject("ledger_frontier_invariants_missing", "BLOCKED")
    required = {
        "SUMMARY_IS_NOT_AUTHORITY",
        "READY_UNCLAIMED_IS_NOT_CLAIM_ADMISSION",
    }
    if not required.issubset(set(invariants)):
        raise Reject("ledger_frontier_invariants_rejected", "BLOCKED")
    return frontier, sha256_obj(frontier)


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


def require_destination_effect_admission(validated: dict[str, Any]) -> None:
    """Block effect-capable dispatch until a trusted destination gate exists.

    This is a user-owned receiver gate, not an OpenAI/ChatGPT hook. The
    currently accepted C-Agent Ledger binding is session + project read only.
    No request/model/transport field can supply destination mutation authority.
    A future allow path requires independently verified Ledger claim/run,
    destination-specific ownership, fencing and atomic version-CAS readback.
    """
    if validated.get("tool") in EFFECT_CAPABLE_TOOLS:
        raise Reject("destination_mutation_admission_unverified", "BLOCKED")


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

    intent_class = env.get("intent_class")
    claim_mode = "model"
    if intent_class is not None:
        if (
            not isinstance(intent_class, str)
            or intent_class not in SUPPORTED_INTENT_CLASSES
        ):
            raise Reject("invalid_intent_class", "FAILED")
        if INTENT_CLASS_BY_TOOL[tool] != intent_class:
            raise Reject("intent_class_tool_mismatch", "BLOCKED")
        claim_mode = "deterministic"

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
    model_calls = budget.get(
        "model_calls",
        0 if claim_mode == "deterministic" else 1,
    )
    local_mcp_calls = budget.get("local_mcp_calls", budget.get("terminal_calls", 1))
    wall_seconds = budget.get("wall_seconds", 120)
    if (
        not isinstance(model_calls, int)
        or isinstance(model_calls, bool)
        or not (0 <= model_calls <= 1)
    ):
        raise Reject("model_call_budget_exceeded", "BLOCKED")
    if claim_mode == "model" and model_calls < 1:
        raise Reject("model_call_budget_required_for_untyped_intent", "BLOCKED")
    if not isinstance(local_mcp_calls, int) or not (1 <= local_mcp_calls <= 1):
        raise Reject("local_mcp_budget_exceeded", "BLOCKED")
    if not isinstance(wall_seconds, int) or not (5 <= wall_seconds <= 300):
        raise Reject("invalid_wall_budget", "BLOCKED")

    return {
        "task_id": task_id,
        "tool": tool,
        "arguments": arguments,
        "authority": authority,
        "intent_class": intent_class,
        "claim_mode": claim_mode,
        "model_call_budget": model_calls,
        "wall_seconds": wall_seconds,
        "deadline": deadline,
    }


def resolve_claim_model() -> str:
    """Resolve the receiver's accepted local claim model.

    Receiver execution identity is intentionally independent from the mutable
    OpenWebUI model-preset table.  The accepted delegation receipt binds this
    receiver to CLAIM_MODEL_ID; changing that identity requires a reviewed
    receiver/configuration change rather than an incidental UI-preset edit.
    """
    req = urllib.request.Request(
        OLLAMA_TAGS,
        headers={"User-Agent": "continuity-delegation-v1/1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            tags = json.loads(r.read())
    except Exception as e:
        raise Reject("ollama_unavailable:" + type(e).__name__, "BLOCKED")
    names = {
        m.get("name")
        for m in tags.get("models", [])
        if isinstance(m, dict)
    }
    if CLAIM_MODEL_ID not in names:
        raise Reject("continuity_agent_base_unavailable", "BLOCKED")
    return CLAIM_MODEL_ID


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
            "seed": CLAIM_MODEL_SEED,
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
        ledger_evidence: list[str] = []
        ledger_calls = 0
        try:
            validated = validate_envelope(env)
            # Stop before even opening a Ledger read session; a project-scoped
            # frontier does not confer destination write authority.
            require_destination_effect_admission(validated)
            remaining = min(
                float(validated["wall_seconds"]),
                float(validated["deadline"] - int(time.time())),
            )
            if remaining <= 0:
                raise Reject("expired", "EXPIRED")

            ledger_session_id, ledger_heartbeat_at = open_ledger_session(
                task_id,
                timeout=min(30.0, remaining),
            )
            ledger_calls = 2
            ledger_evidence = [
                "ledger_session:" + ledger_session_id,
                "ledger_session_heartbeat:" + ledger_heartbeat_at,
            ]

            elapsed = time.monotonic() - started
            remaining = min(
                float(validated["wall_seconds"]) - elapsed,
                float(validated["deadline"] - int(time.time())),
            )
            if remaining <= 0:
                raise Reject("expired_after_ledger_session", "EXPIRED")

            _, frontier_sha256 = read_ledger_frontier(
                task_id,
                ledger_session_id,
                timeout=min(15.0, remaining),
            )
            ledger_calls = 3
            ledger_evidence.append(
                "ledger_frontier_sha256:" + frontier_sha256
            )

            elapsed = time.monotonic() - started
            remaining = min(
                float(validated["wall_seconds"]) - elapsed,
                float(validated["deadline"] - int(time.time())),
            )
            if remaining <= 0:
                raise Reject("expired_after_ledger_frontier", "EXPIRED")

            if validated["claim_mode"] == "deterministic":
                claim = {
                    "task_id": validated["task_id"],
                    "decision": "CLAIM",
                    "capability": validated["tool"],
                }
                model_ms = 0
                model_calls = 0
                claim_evidence_prefix = "deterministic_claim_sha256:"
            else:
                model_id = resolve_claim_model()
                claim, model_ms = claim_task(
                    env,
                    validated,
                    model_id,
                    min(30.0, remaining),
                )
                model_calls = 1
                claim_evidence_prefix = "claim_sha256:"

            claim_digest = sha256_obj(claim)
            claim_evidence = claim_evidence_prefix + claim_digest
            if claim["decision"] != "CLAIM":
                receipt = make_receipt(
                    task_id,
                    model_id=model_id,
                    evidence_refs=ledger_evidence + [claim_evidence],
                    unresolved=["agent_declined"],
                    resource_usage={
                        "ledger_calls": ledger_calls,
                        "model_calls": model_calls,
                        "local_mcp_calls": 0,
                        "model_ms": model_ms,
                    },
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
                    evidence_refs=ledger_evidence + [claim_evidence],
                    result=result,
                    unresolved=unresolved,
                    resource_usage={
                        "ledger_calls": ledger_calls,
                        "model_calls": model_calls,
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
                evidence_refs=ledger_evidence,
                unresolved=[e.code],
                resource_usage={
                    "ledger_calls": ledger_calls,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                },
                completion_state=e.completion_state,
            )
        except Exception as e:
            receipt = make_receipt(
                task_id,
                model_id=model_id,
                evidence_refs=ledger_evidence,
                unresolved=[type(e).__name__ + ":" + str(e)[:500]],
                resource_usage={
                    "ledger_calls": ledger_calls,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                },
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

    typed = dict(
        base,
        task_id="selftest-typed",
        intent_class="filesystem_read",
        resource_budget={
            "model_calls": 0,
            "local_mcp_calls": 1,
            "wall_seconds": 30,
        },
    )
    typed_validated = validate_envelope(typed, now)
    assert typed_validated["claim_mode"] == "deterministic"
    assert typed_validated["model_call_budget"] == 0

    mismatch = dict(
        typed,
        task_id="selftest-intent-mismatch",
        intent_class="runtime_health",
    )
    try:
        validate_envelope(mismatch, now)
        raise AssertionError("intent/tool mismatch accepted")
    except Reject as e:
        assert e.code == "intent_class_tool_mismatch"

    untyped_zero_model = dict(
        base,
        task_id="selftest-untyped-zero-model",
        resource_budget={
            "model_calls": 0,
            "local_mcp_calls": 1,
            "wall_seconds": 30,
        },
    )
    try:
        validate_envelope(untyped_zero_model, now)
        raise AssertionError("untyped request without model budget accepted")
    except Reject as e:
        assert e.code == "model_call_budget_required_for_untyped_intent"

    assert _ledger_task_key("selftest-1") == _ledger_task_key("selftest-1")
    assert _ledger_task_key("selftest-1") != _ledger_task_key("selftest-2")
    assert len(_ledger_task_key("selftest-1")) == 24

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
