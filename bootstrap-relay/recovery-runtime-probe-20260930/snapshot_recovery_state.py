#!/usr/bin/env python3
"""Compose read-only OpenWebUI recovery evidence into one deterministic snapshot."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from collect_ollama_evidence import collect_ollama_evidence
from collect_local_agent_binding import collect_local_agent_binding
from collect_frontend_voice_evidence import collect_frontend_voice_evidence
from recovery_functions import recovery_decision

SCHEMA = "openwebui-recovery-snapshot-v1"


def snapshot_recovery_state(
    ollama_collector: Callable[[], dict[str, Any]] = collect_ollama_evidence,
    binding_collector: Callable[[], dict[str, Any]] = collect_local_agent_binding,
    frontend_voice_collector: Callable[[], dict[str, Any]] = collect_frontend_voice_evidence,
    decision_fn: Callable[[dict[str, Any]], dict[str, Any]] = recovery_decision,
) -> dict[str, Any]:
    """Return one compact recovery snapshot without mutating runtime state."""
    ollama = dict(ollama_collector() or {})
    binding = dict(binding_collector() or {})
    frontend_voice = dict(frontend_voice_collector() or {})

    ollama["configured_base_urls"] = binding.get("ollama_base_urls")
    workspace_models = binding.get("rows") or []
    frontend = frontend_voice.get("frontend") or {}
    voice_sources = frontend_voice.get("voice_sources") or []

    classifier_input = {
        "ollama": ollama,
        "workspace_models": workspace_models,
        "frontend": frontend,
        "voice_sources": voice_sources,
    }
    decision = decision_fn(classifier_input)

    evidence = {
        "ollama": {
            "port_open": ollama.get("port_open"),
            "process_running": ollama.get("process_running"),
            "processes": ollama.get("processes") or [],
            "version_http": ollama.get("version_http"),
            "version": ollama.get("version"),
            "tags_http": ollama.get("tags_http"),
            "models": ollama.get("models") or [],
            "ollama_on_path": ollama.get("ollama_on_path"),
            "launcher_candidates": ollama.get("launcher_candidates") or [],
            "log_candidates": ollama.get("log_candidates") or [],
            "configured_base_urls": ollama.get("configured_base_urls"),
        },
        "local_agent_binding": {
            "state": binding.get("state"),
            "db": binding.get("db"),
            "row_count": binding.get("row_count"),
            "rows": workspace_models,
            "ollama_base_urls": binding.get("ollama_base_urls"),
        },
        "frontend": frontend,
        "voice_source_names": frontend_voice.get("voice_source_names") or [],
    }

    return {
        "schema": SCHEMA,
        "captured_at_unix": int(time.time()),
        "mutation": "NONE",
        "evidence": evidence,
        "decision": decision,
    }


def main() -> int:
    try:
        result = snapshot_recovery_state()
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        print(json.dumps({
            "schema": SCHEMA,
            "state": "ERROR",
            "error": type(exc).__name__,
            "detail": str(exc),
            "mutation": "NONE",
        }, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
