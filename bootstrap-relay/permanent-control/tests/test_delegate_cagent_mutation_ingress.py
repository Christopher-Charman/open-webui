"""The owned Continuity-Agent receiver cannot infer mutation grants from Ledger reads."""
from __future__ import annotations

import importlib.util
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "delegate-cagent.py"
spec = importlib.util.spec_from_file_location("receiver_mutation_bound", SOURCE)
assert spec is not None and spec.loader is not None
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)


def envelope(tool="terminal_exec", *, task_id="receiver-terminal-admission-unique1"):
    return {
        "task_id": task_id,
        "origin_runtime_identity": "test-origin",
        "target_agent_identity": receiver.AGENT_ID,
        "objective": "Run one delegated action.",
        "intent_class": "bounded_operator_command" if tool == "terminal_exec"
                        else "runtime_health",
        "evidence_refs": [],
        "authority_ceiling": "bounded_operator" if tool == "terminal_exec"
                              else "read_only",
        "allowed_capability_profile": [tool],
        "resource_budget": {"model_calls": 0, "local_mcp_calls": 1,
                            "wall_seconds": 30},
        "deadline": int(time.time()) + 120,
        "expected_result_schema": receiver.RECEIPT_SCHEMA,
        "return_route": "stdout",
        "requested_action": {
            "tool": tool, "arguments":
                {"command": "true", "timeout_ms": 1000}
                if tool == "terminal_exec" else {},
        },
        "delegation_depth": 0,
    }


class ReceiverMutationIngressTests(unittest.TestCase):
    def test_terminal_envelope_still_valid_structurally_but_not_authorized(self):
        validated = receiver.validate_envelope(envelope())
        self.assertEqual(validated["tool"], "terminal_exec")
        with self.assertRaises(receiver.Reject) as cm:
            receiver.require_destination_effect_admission(validated)
        self.assertEqual(cm.exception.code, "destination_mutation_admission_unverified")
        self.assertEqual(cm.exception.completion_state, "BLOCKED")

    def test_model_claim_or_envelope_hints_cannot_bypass(self):
        for extra in (
            {"ledger_claim": "claim:any", "fencing_token": "token"},
            {"global_idle_verified": True},
            {"destination_authorization": {"decision": "ALLOW"}},
        ):
            with self.subTest(extra=extra):
                env = envelope()
                env.update(extra)
                validated = receiver.validate_envelope(env)
                with self.assertRaises(receiver.Reject):
                    receiver.require_destination_effect_admission(validated)

    def test_terminal_denial_occurs_without_ledger_open_or_mcp_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(receiver, "STATE", Path(tmp)), patch.object(
                receiver, "open_ledger_session", side_effect=AssertionError("ledger called")
            ), patch.object(
                receiver, "call_local_mcp", side_effect=AssertionError("mcp called")
            ):
                env = envelope()
                receipt = receiver.run(env)
                self.assertEqual(receipt["completion_state"], "BLOCKED")
                self.assertIn("destination_mutation_admission_unverified",
                              receipt["unresolved"])
                self.assertEqual(receipt["actions"], [])
                self.assertEqual(receipt["resource_usage"]["ledger_calls"], 0)
                self.assertFalse(receipt["result"])
                second = receiver.run(env)
                self.assertEqual(second, receipt)

    def test_readonly_tool_admitted_by_destination_filter(self):
        validated = receiver.validate_envelope(envelope("runtime_health"))
        self.assertIsNone(receiver.require_destination_effect_admission(validated))


if __name__ == "__main__":
    unittest.main()
