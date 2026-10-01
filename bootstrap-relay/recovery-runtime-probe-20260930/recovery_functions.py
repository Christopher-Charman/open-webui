#!/usr/bin/env python3
"""Deterministic recovery classifiers for the PowerPC OpenWebUI lane.

These helpers deliberately avoid mutation. They convert raw probe evidence into
machine-readable classifications so higher-level reasoning is reserved for
ambiguous recovery decisions.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any, Iterable

QWEN_TARGET = "qwen2.5-coder:1.5b-instruct-q4_K_M"
DEEPSEEK_FALLBACKS = (
    "deepseek-r1:1.5b-qwen-distill-q8_0",
    "deepseek-r1:1.5b",
)
FORBIDDEN_LOCAL_AGENT_FAMILIES = ("granite",)
LOCAL_AGENT_TOKENS = ("local agent", "mini c-agent", "c-agent")

ACCEPTED_POSTMOUNT_MARKER = "owui-postmount-ui-voice-v20260929.1"
BINDER_V2_MARKER = "continuity-shell-semantic-binder-v20260930.2"
REGRESSED_HERO_MARKER = "continuity-shell-landing-hero-presenter-v20260930.4"

VOICE_PATTERNS = {
    "warm_helper": re.compile(r"\bwarmSelectedVoice\b"),
    "warm_endpoint": re.compile(r"/api/v1/audio/local-voice/warm"),
    "speech_synthesis": re.compile(r"\bspeechSynthesis\b"),
    "new_audio": re.compile(r"\bnew\s+Audio\s*\("),
    "audio_play": re.compile(r"\.play\s*\("),
    "cortana_literal": re.compile(r"\bcortana\b", re.I),
    "ready_literal": re.compile(r"\bready\b", re.I),
}


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _norm(value).lower()


def _status_ok(value: Any) -> bool:
    try:
        code = int(value)
    except (TypeError, ValueError):
        return False
    return 200 <= code < 300


def classify_ollama(evidence: dict[str, Any]) -> dict[str, Any]:
    """Classify Ollama from raw listener/process/HTTP evidence.

    Required/accepted fields:
      port_open: bool | None
      process_running: bool | None
      version_http: int | None
      tags_http: int | None
      models: list[str]
      configured_base_urls: list[str] | str | None
    """
    port_open = evidence.get("port_open")
    process_running = evidence.get("process_running")
    version_ok = _status_ok(evidence.get("version_http"))
    tags_ok = _status_ok(evidence.get("tags_http"))
    models = [_norm(x) for x in evidence.get("models", []) if _norm(x)]

    if port_open is False and process_running is False:
        state = "DOWN_NO_PROCESS"
        next_action = "INSPECT_CANONICAL_LAUNCHER"
    elif port_open is False and process_running is True:
        state = "PROCESS_PRESENT_NO_LISTENER"
        next_action = "INSPECT_PROCESS_ARGS_AND_LOGS"
    elif port_open is True and not (version_ok or tags_ok):
        state = "LISTENER_UP_HTTP_UNHEALTHY"
        next_action = "INSPECT_OLLAMA_HTTP_FAILURE"
    elif port_open is True and tags_ok:
        state = "HEALTHY"
        next_action = "VERIFY_MODEL_INVENTORY_AND_BINDING"
    else:
        state = "INDETERMINATE"
        next_action = "COLLECT_LISTENER_PROCESS_HTTP_EVIDENCE"

    configured = evidence.get("configured_base_urls")
    if isinstance(configured, str):
        configured_urls = [configured]
    else:
        configured_urls = [_norm(x) for x in (configured or []) if _norm(x)]
    endpoint_expected = "http://127.0.0.1:11434"
    endpoint_match = (
        None if not configured_urls
        else any(u.rstrip("/") == endpoint_expected for u in configured_urls)
    )

    return {
        "state": state,
        "next_action": next_action,
        "port_open": port_open,
        "process_running": process_running,
        "version_http_ok": version_ok,
        "tags_http_ok": tags_ok,
        "model_count": len(models),
        "endpoint_expected": endpoint_expected,
        "endpoint_match": endpoint_match,
    }


def select_small_local_model(inventory: Iterable[str]) -> dict[str, Any]:
    """Choose a small Local Agent model by explicit recovery policy.

    Policy:
      1. exact Qwen 2.5 Coder target;
      2. DeepSeek 1.5B fallback(s);
      3. never Granite for this role.
    """
    models = [_norm(x) for x in inventory if _norm(x)]
    by_lower = {_lower(x): x for x in models}

    if _lower(QWEN_TARGET) in by_lower:
        return {
            "state": "SELECTED",
            "model": by_lower[_lower(QWEN_TARGET)],
            "reason": "preferred_qwen_target_present",
            "requires_pull": False,
        }

    for candidate in DEEPSEEK_FALLBACKS:
        if _lower(candidate) in by_lower:
            return {
                "state": "FALLBACK_SELECTED",
                "model": by_lower[_lower(candidate)],
                "reason": "qwen_absent_deepseek_present",
                "requires_pull": False,
            }

    forbidden_present = sorted(
        x for x in models if any(tok in _lower(x) for tok in FORBIDDEN_LOCAL_AGENT_FAMILIES)
    )
    return {
        "state": "NO_APPROVED_SMALL_MODEL_PRESENT",
        "model": None,
        "reason": "approved_targets_absent",
        "requires_pull": True,
        "forbidden_present": forbidden_present,
    }


def identify_local_agent_binding(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fail closed unless exactly one Local Agent / Mini C-Agent workspace row matches."""
    matches: list[dict[str, Any]] = []
    for row in rows:
        blob = " ".join(
            _lower(row.get(k)) for k in ("id", "name", "base_model_id")
        )
        if any(tok in blob for tok in LOCAL_AGENT_TOKENS):
            matches.append({
                "id": row.get("id"),
                "name": row.get("name"),
                "base_model_id": row.get("base_model_id"),
                "is_active": row.get("is_active"),
            })

    if len(matches) == 1:
        m = matches[0]
        forbidden = any(
            tok in _lower(m.get("base_model_id"))
            for tok in FORBIDDEN_LOCAL_AGENT_FAMILIES
        )
        return {
            "state": "UNIQUE",
            "row": m,
            "forbidden_current_binding": forbidden,
        }
    if not matches:
        return {"state": "NOT_FOUND", "rows": []}
    return {"state": "AMBIGUOUS", "rows": matches}


def plan_local_agent_rebind(
    rows: Iterable[dict[str, Any]],
    inventory: Iterable[str],
) -> dict[str, Any]:
    """Return a mutation plan only when row identity and target inventory are unambiguous."""
    binding = identify_local_agent_binding(rows)
    selection = select_small_local_model(inventory)

    if binding["state"] != "UNIQUE":
        return {
            "state": "BLOCKED",
            "reason": "local_agent_row_" + binding["state"].lower(),
            "binding": binding,
            "selection": selection,
        }
    if selection["state"] not in ("SELECTED", "FALLBACK_SELECTED"):
        return {
            "state": "BLOCKED",
            "reason": "approved_target_not_present",
            "binding": binding,
            "selection": selection,
        }

    row = binding["row"]
    current = _norm(row.get("base_model_id"))
    target = _norm(selection["model"])
    if _lower(current) == _lower(target):
        return {
            "state": "NOOP",
            "reason": "already_bound",
            "row_id": row.get("id"),
            "current": current,
            "target": target,
        }

    return {
        "state": "READY",
        "reason": "single_field_compare_and_swap",
        "row_id": row.get("id"),
        "expected_current_base_model_id": current,
        "target_base_model_id": target,
        "allowed_fields": ["base_model_id", "updated_at"],
        "requires_restart": False,
        "requires_model_pull": False,
    }


def classify_frontend(evidence: dict[str, Any]) -> dict[str, Any]:
    """Classify the protected frontend/post-mount generation."""
    loader_bytes = evidence.get("loader_bytes")
    custom_css_bytes = evidence.get("custom_css_bytes")
    markers = evidence.get("markers") or {}

    stock_bootstrap_inert = loader_bytes == 0 and custom_css_bytes == 0
    accepted_postmount = bool(markers.get(ACCEPTED_POSTMOUNT_MARKER))
    binder_v2 = bool(markers.get(BINDER_V2_MARKER))
    regressed_hero = bool(markers.get(REGRESSED_HERO_MARKER))

    if not stock_bootstrap_inert:
        state = "STOCK_BOOTSTRAP_MUTATED"
    elif regressed_hero:
        state = "POSTMOUNT_REGRESSED_HERO_PRESENT"
    elif accepted_postmount:
        state = "ACCEPTED_POSTMOUNT_BASE_PRESENT"
    else:
        state = "UNBOUND_GENERATION"

    return {
        "state": state,
        "stock_bootstrap_inert": stock_bootstrap_inert,
        "accepted_postmount": accepted_postmount,
        "binder_v2": binder_v2,
        "regressed_hero": regressed_hero,
    }


def classify_voice_startup(texts: Iterable[str]) -> dict[str, Any]:
    """Return deterministic source-level trigger flags; does not infer audible behavior."""
    combined = "\n".join(_norm(x) for x in texts)
    flags = {name: bool(pattern.search(combined)) for name, pattern in VOICE_PATTERNS.items()}

    if flags["warm_helper"] or flags["warm_endpoint"]:
        state = "WARM_PATH_PRESENT"
    elif flags["audio_play"] or flags["speech_synthesis"] or flags["new_audio"]:
        state = "PLAYBACK_PRIMITIVE_PRESENT"
    else:
        state = "NO_STATIC_PLAYBACK_PRIMITIVE_FOUND"

    return {
        "state": state,
        "flags": flags,
        "audible_ready_candidate": bool(
            flags["ready_literal"]
            and flags["cortana_literal"]
            and (flags["audio_play"] or flags["speech_synthesis"] or flags["new_audio"])
        ),
    }


def recovery_decision(evidence: dict[str, Any]) -> dict[str, Any]:
    """Compose low-level classifiers into a fail-closed recovery decision."""
    ollama = classify_ollama(evidence.get("ollama") or {})
    model_plan = plan_local_agent_rebind(
        evidence.get("workspace_models") or [],
        (evidence.get("ollama") or {}).get("models") or [],
    )
    frontend = classify_frontend(evidence.get("frontend") or {})
    voice = classify_voice_startup(evidence.get("voice_sources") or [])

    if ollama["state"] != "HEALTHY":
        next_action = ollama["next_action"]
        mutation_gate = "BLOCK_MODEL_REBIND"
    elif model_plan["state"] == "READY":
        next_action = "REBIND_LOCAL_AGENT_COMPARE_AND_SWAP"
        mutation_gate = "ALLOW_ONLY_MODEL_BINDING_FIELDS"
    elif model_plan["state"] == "NOOP":
        next_action = "VALIDATE_LOCAL_AGENT_DIRECT_INFERENCE"
        mutation_gate = "NO_MODEL_MUTATION"
    else:
        next_action = "RESOLVE_MODEL_BINDING_AMBIGUITY"
        mutation_gate = "BLOCK_MODEL_REBIND"

    return {
        "ollama": ollama,
        "local_agent": model_plan,
        "frontend": frontend,
        "voice": voice,
        "next_action": next_action,
        "mutation_gate": mutation_gate,
    }


def main() -> int:
    try:
        evidence = json.load(sys.stdin)
        result = recovery_decision(evidence)
        json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        json.dump(
            {"state": "ERROR", "error": type(exc).__name__, "detail": str(exc)},
            sys.stdout,
            sort_keys=True,
            separators=(",", ":"),
        )
        sys.stdout.write("\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
