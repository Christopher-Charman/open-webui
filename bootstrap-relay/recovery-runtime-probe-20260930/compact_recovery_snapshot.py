#!/usr/bin/env python3
"""Emit a compact, audit-friendly OpenWebUI recovery decision snapshot."""

from __future__ import annotations

import json

from snapshot_recovery_state import snapshot_recovery_state


def compact_recovery_snapshot(snapshot: dict) -> dict:
    evidence = snapshot.get("evidence") or {}
    ollama = evidence.get("ollama") or {}
    binding = evidence.get("local_agent_binding") or {}
    frontend = evidence.get("frontend") or {}
    markers = frontend.get("markers") or {}

    return {
        "schema": "openwebui-recovery-compact-v1",
        "captured_at_unix": snapshot.get("captured_at_unix"),
        "mutation": snapshot.get("mutation"),
        "decision": snapshot.get("decision"),
        "audit": {
            "ollama": {
                "port_open": ollama.get("port_open"),
                "process_running": ollama.get("process_running"),
                "version_http": ollama.get("version_http"),
                "tags_http": ollama.get("tags_http"),
                "model_count": len(ollama.get("models") or []),
                "models": ollama.get("models") or [],
                "configured_base_urls": ollama.get("configured_base_urls"),
                "ollama_on_path": ollama.get("ollama_on_path"),
                "launcher_candidates": ollama.get("launcher_candidates") or [],
            },
            "local_agent": {
                "state": binding.get("state"),
                "row_count": binding.get("row_count"),
                "rows": binding.get("rows") or [],
            },
            "frontend": {
                "loader_bytes": frontend.get("loader_bytes"),
                "custom_css_bytes": frontend.get("custom_css_bytes"),
                "index_sha256": frontend.get("index_sha256"),
                "accepted_postmount_marker": markers.get("owui-postmount-ui-voice-v20260929.1", 0),
                "binder_v2_marker": markers.get("continuity-shell-semantic-binder-v20260930.2", 0),
                "regressed_hero_marker": markers.get("continuity-shell-landing-hero-presenter-v20260930.4", 0),
            },
            "voice_source_names": evidence.get("voice_source_names") or [],
        },
    }


def main() -> int:
    try:
        out = compact_recovery_snapshot(snapshot_recovery_state())
        print(json.dumps(out, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        print(json.dumps({
            "schema": "openwebui-recovery-compact-v1",
            "state": "ERROR",
            "error": type(exc).__name__,
            "detail": str(exc),
            "mutation": "NONE",
        }, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
