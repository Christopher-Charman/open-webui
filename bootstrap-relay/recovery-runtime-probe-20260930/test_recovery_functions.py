#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("recovery_functions", HERE / "recovery_functions.py")
rf = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(rf)


class RecoveryFunctionsTests(unittest.TestCase):
    def test_ollama_down_blocks_rebind(self):
        out = rf.recovery_decision({
            "ollama": {
                "port_open": False,
                "process_running": False,
                "version_http": None,
                "tags_http": None,
                "models": [rf.QWEN_TARGET],
            },
            "workspace_models": [{
                "id": "local-agent",
                "name": "Local Agent",
                "base_model_id": "granite:latest",
                "is_active": True,
            }],
        })
        self.assertEqual(out["ollama"]["state"], "DOWN_NO_PROCESS")
        self.assertEqual(out["mutation_gate"], "BLOCK_MODEL_REBIND")
        self.assertEqual(out["next_action"], "INSPECT_CANONICAL_LAUNCHER")

    def test_qwen_preferred_over_deepseek_and_granite(self):
        out = rf.select_small_local_model([
            "granite3.3:2b",
            "deepseek-r1:1.5b",
            rf.QWEN_TARGET,
        ])
        self.assertEqual(out["state"], "SELECTED")
        self.assertEqual(out["model"], rf.QWEN_TARGET)
        self.assertFalse(out["requires_pull"])

    def test_deepseek_fallback_when_qwen_absent(self):
        out = rf.select_small_local_model([
            "granite3.3:2b",
            "deepseek-r1:1.5b",
        ])
        self.assertEqual(out["state"], "FALLBACK_SELECTED")
        self.assertEqual(out["model"], "deepseek-r1:1.5b")

    def test_granite_never_selected(self):
        out = rf.select_small_local_model(["granite3.3:2b"])
        self.assertEqual(out["state"], "NO_APPROVED_SMALL_MODEL_PRESENT")
        self.assertIsNone(out["model"])
        self.assertIn("granite3.3:2b", out["forbidden_present"])

    def test_binding_must_be_unique(self):
        out = rf.identify_local_agent_binding([
            {"id": "local-agent-a", "name": "Local Agent", "base_model_id": "x"},
            {"id": "mini-c-agent", "name": "Mini C-Agent", "base_model_id": "y"},
        ])
        self.assertEqual(out["state"], "AMBIGUOUS")

    def test_rebind_plan_is_two_field_only(self):
        out = rf.plan_local_agent_rebind(
            [{
                "id": "local-agent",
                "name": "Local Agent",
                "base_model_id": "granite3.3:2b",
                "is_active": True,
            }],
            [rf.QWEN_TARGET],
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["row_id"], "local-agent")
        self.assertEqual(out["target_base_model_id"], rf.QWEN_TARGET)
        self.assertEqual(out["allowed_fields"], ["base_model_id", "updated_at"])
        self.assertFalse(out["requires_restart"])
        self.assertFalse(out["requires_model_pull"])

    def test_rebind_noop_when_already_qwen(self):
        out = rf.plan_local_agent_rebind(
            [{
                "id": "local-agent",
                "name": "Local Agent",
                "base_model_id": rf.QWEN_TARGET,
                "is_active": True,
            }],
            [rf.QWEN_TARGET],
        )
        self.assertEqual(out["state"], "NOOP")

    def test_frontend_detects_regressed_hero(self):
        out = rf.classify_frontend({
            "loader_bytes": 0,
            "custom_css_bytes": 0,
            "markers": {
                rf.ACCEPTED_POSTMOUNT_MARKER: True,
                rf.BINDER_V2_MARKER: True,
                rf.REGRESSED_HERO_MARKER: True,
            },
        })
        self.assertEqual(out["state"], "POSTMOUNT_REGRESSED_HERO_PRESENT")
        self.assertTrue(out["stock_bootstrap_inert"])

    def test_frontend_fails_if_stock_bootstrap_mutated(self):
        out = rf.classify_frontend({
            "loader_bytes": 12,
            "custom_css_bytes": 0,
            "markers": {},
        })
        self.assertEqual(out["state"], "STOCK_BOOTSTRAP_MUTATED")

    def test_voice_flags_audible_ready_candidate(self):
        out = rf.classify_voice_startup([
            "const voice='cortana'; const msg='ready'; new Audio(url).play();"
        ])
        self.assertEqual(out["state"], "PLAYBACK_PRIMITIVE_PRESENT")
        self.assertTrue(out["audible_ready_candidate"])

    def test_voice_nowarm_baseline(self):
        out = rf.classify_voice_startup([
            "const VERSION='1.3.4-nowarm';"
        ])
        self.assertEqual(out["state"], "NO_STATIC_PLAYBACK_PRIMITIVE_FOUND")
        self.assertFalse(out["audible_ready_candidate"])


if __name__ == "__main__":
    unittest.main()
