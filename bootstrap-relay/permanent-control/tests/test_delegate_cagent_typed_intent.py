from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "delegate-cagent.py"
SPEC = importlib.util.spec_from_file_location("delegate_cagent_typed", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
delegate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(delegate)


def typed_envelope(task_id: str = "typed-intent-test-0001"):
    now = 2_000_000_000
    return {
        "task_id": task_id,
        "origin_runtime_identity": "test-origin",
        "target_agent_identity": delegate.AGENT_ID,
        "objective": "Read a bounded file.",
        "intent_class": "filesystem_read",
        "evidence_refs": [],
        "authority_ceiling": "read_only",
        "allowed_capability_profile": ["read_text"],
        "resource_budget": {
            "model_calls": 0,
            "local_mcp_calls": 1,
            "wall_seconds": 30,
        },
        "deadline": now + 60,
        "expected_result_schema": delegate.RECEIPT_SCHEMA,
        "return_route": "stdout",
        "requested_action": {
            "tool": "read_text",
            "arguments": {"path": "README.md"},
        },
        "delegation_depth": 0,
    }


class ContinuityAgentTypedIntentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_state = delegate.STATE
        delegate.STATE = Path(self.tmp.name)

    def tearDown(self) -> None:
        delegate.STATE = self.old_state
        self.tmp.cleanup()

    def test_typed_intent_compiles_to_deterministic_claim(self):
        validated = delegate.validate_envelope(
            typed_envelope(),
            now=2_000_000_000,
        )
        self.assertEqual(validated["claim_mode"], "deterministic")
        self.assertEqual(validated["model_call_budget"], 0)
        self.assertEqual(validated["intent_class"], "filesystem_read")

    def test_intent_tool_mismatch_fails_closed(self):
        env = typed_envelope("typed-intent-mismatch-0001")
        env["intent_class"] = "runtime_health"
        with self.assertRaises(delegate.Reject) as caught:
            delegate.validate_envelope(env, now=2_000_000_000)
        self.assertEqual(caught.exception.code, "intent_class_tool_mismatch")
        self.assertEqual(caught.exception.completion_state, "BLOCKED")

    def test_untyped_request_needs_model_budget(self):
        env = typed_envelope("untyped-zero-model-0001")
        env.pop("intent_class")
        with self.assertRaises(delegate.Reject) as caught:
            delegate.validate_envelope(env, now=2_000_000_000)
        self.assertEqual(
            caught.exception.code,
            "model_call_budget_required_for_untyped_intent",
        )

    def test_typed_run_never_calls_claim_model(self):
        events = []

        def open_session(task_id, *, timeout):
            events.append(("ledger", task_id))
            return "session:typed", "2026-10-06T14:00:00Z"

        def read_frontier(task_id, session_id, *, timeout):
            events.append(("frontier", task_id))
            return (
                {
                    "project_id": delegate.LEDGER_PROJECT_ID,
                    "filters": {
                        "owner_actor_id": None,
                        "limit": delegate.LEDGER_FRONTIER_LIMIT,
                    },
                    "counts": {},
                    "tasks": [],
                    "blockers": [],
                    "conflicts": [],
                    "handoffs": [],
                    "leases": [],
                    "receipt_refs": [],
                    "invariants": [
                        "SUMMARY_IS_NOT_AUTHORITY",
                        "READY_UNCLAIMED_IS_NOT_CLAIM_ADMISSION",
                    ],
                },
                "b" * 64,
            )

        def local_mcp(tool, arguments, timeout):
            events.append(("mcp", tool))
            return {
                "isError": False,
                "content": [{"type": "text", "text": "ok"}],
            }, 2

        with (
            patch.object(delegate.time, "time", return_value=2_000_000_000),
            patch.object(delegate, "open_ledger_session", side_effect=open_session),
            patch.object(delegate, "read_ledger_frontier", side_effect=read_frontier),
            patch.object(delegate, "resolve_claim_model") as resolve_model,
            patch.object(delegate, "claim_task") as model_claim,
            patch.object(delegate, "call_local_mcp", side_effect=local_mcp),
        ):
            receipt = delegate.run(typed_envelope())

        self.assertEqual(receipt["completion_state"], "COMPLETED")
        self.assertEqual(
            [name for name, _ in events],
            ["ledger", "frontier", "mcp"],
        )
        resolve_model.assert_not_called()
        model_claim.assert_not_called()
        self.assertEqual(receipt["resource_usage"]["model_calls"], 0)
        self.assertEqual(receipt["executor_identity"]["model_id"], None)
        self.assertTrue(
            any(
                ref.startswith("deterministic_claim_sha256:")
                for ref in receipt["evidence_refs"]
            )
        )


if __name__ == "__main__":
    unittest.main()
