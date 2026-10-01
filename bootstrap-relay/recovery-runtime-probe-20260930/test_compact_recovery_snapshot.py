#!/usr/bin/env python3
import importlib.util
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SPEC = importlib.util.spec_from_file_location(
    "compact_recovery_snapshot",
    HERE / "compact_recovery_snapshot.py",
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class CompactRecoverySnapshotTests(unittest.TestCase):
    def test_compacts_raw_snapshot(self):
        raw = {
            "captured_at_unix": 123,
            "mutation": "NONE",
            "decision": {"next_action": "INSPECT_CANONICAL_LAUNCHER"},
            "evidence": {
                "ollama": {
                    "port_open": False,
                    "process_running": False,
                    "version_http": None,
                    "tags_http": None,
                    "models": ["qwen2.5-coder:1.5b-instruct-q4_K_M"],
                    "configured_base_urls": ["http://127.0.0.1:11434"],
                    "ollama_on_path": "/x/ollama",
                    "launcher_candidates": [{"path": "/x/run-ollama.sh"}],
                    "log_candidates": [{"path": "/x/log","tail":["large"]}],
                },
                "local_agent_binding": {
                    "state": "OK",
                    "row_count": 1,
                    "rows": [{"id":"local-agent","base_model_id":"granite3.3:2b"}],
                },
                "frontend": {
                    "loader_bytes": 0,
                    "custom_css_bytes": 0,
                    "index_sha256": "abc",
                    "markers": {
                        "owui-postmount-ui-voice-v20260929.1": 1,
                        "continuity-shell-semantic-binder-v20260930.2": 1,
                        "continuity-shell-landing-hero-presenter-v20260930.4": 1,
                    },
                    "assets": {"large":"omitted"},
                },
                "voice_source_names": ["pwa-voice-bridge.js"],
            },
        }
        out = mod.compact_recovery_snapshot(raw)
        self.assertEqual(out["schema"], "openwebui-recovery-compact-v1")
        self.assertEqual(out["audit"]["ollama"]["model_count"], 1)
        self.assertNotIn("log_candidates", out["audit"]["ollama"])
        self.assertNotIn("assets", out["audit"]["frontend"])
        self.assertEqual(out["audit"]["frontend"]["regressed_hero_marker"], 1)


if __name__ == "__main__":
    unittest.main()
