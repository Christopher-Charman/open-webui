#!/usr/bin/env python3
import importlib.util
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SPEC = importlib.util.spec_from_file_location(
    "snapshot_recovery_state",
    HERE / "snapshot_recovery_state.py",
)
snap = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(snap)


class SnapshotRecoveryStateTests(unittest.TestCase):
    def test_composes_collectors_and_classifier(self):
        seen = {}

        def ollama():
            return {
                "port_open": True,
                "process_running": True,
                "version_http": 200,
                "tags_http": 200,
                "models": ["qwen2.5-coder:1.5b-instruct-q4_K_M"],
                "processes": ["123 ollama serve"],
            }

        def binding():
            return {
                "state": "OK",
                "db": "/tmp/webui.db",
                "row_count": 1,
                "rows": [{
                    "id": "local-agent",
                    "name": "Local Agent",
                    "base_model_id": "granite3.3:2b",
                    "is_active": True,
                }],
                "ollama_base_urls": ["http://127.0.0.1:11434"],
            }

        def frontend_voice():
            return {
                "frontend": {
                    "loader_bytes": 0,
                    "custom_css_bytes": 0,
                    "markers": {
                        "owui-postmount-ui-voice-v20260929.1": 1,
                    },
                },
                "voice_sources": ["const VERSION='1.3.4-nowarm';"],
                "voice_source_names": ["pwa-voice-bridge.js"],
            }

        def decision(inp):
            seen["input"] = inp
            return {"next_action": "REBIND_LOCAL_AGENT_COMPARE_AND_SWAP"}

        out = snap.snapshot_recovery_state(
            ollama_collector=ollama,
            binding_collector=binding,
            frontend_voice_collector=frontend_voice,
            decision_fn=decision,
        )

        self.assertEqual(out["schema"], "openwebui-recovery-snapshot-v1")
        self.assertEqual(out["mutation"], "NONE")
        self.assertEqual(
            seen["input"]["ollama"]["configured_base_urls"],
            ["http://127.0.0.1:11434"],
        )
        self.assertEqual(
            out["evidence"]["local_agent_binding"]["rows"][0]["id"],
            "local-agent",
        )
        self.assertEqual(
            out["decision"]["next_action"],
            "REBIND_LOCAL_AGENT_COMPARE_AND_SWAP",
        )

    def test_empty_collectors_fail_closed_through_classifier(self):
        out = snap.snapshot_recovery_state(
            ollama_collector=lambda: {},
            binding_collector=lambda: {},
            frontend_voice_collector=lambda: {},
            decision_fn=lambda inp: {
                "next_action": "COLLECT_LISTENER_PROCESS_HTTP_EVIDENCE",
                "mutation_gate": "BLOCK_MODEL_REBIND",
            },
        )
        self.assertEqual(
            out["decision"]["mutation_gate"],
            "BLOCK_MODEL_REBIND",
        )
        self.assertEqual(out["evidence"]["ollama"]["models"], [])


if __name__ == "__main__":
    unittest.main()
