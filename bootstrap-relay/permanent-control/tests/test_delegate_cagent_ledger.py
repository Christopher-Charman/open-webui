from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "delegate-cagent.py"
SPEC = importlib.util.spec_from_file_location("delegate_cagent", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
delegate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(delegate)


def envelope(task_id: str = "ledger-session-test-0001"):
    now = 2_000_000_000
    return {
        "task_id": task_id,
        "origin_runtime_identity": "test-origin",
        "target_agent_identity": delegate.AGENT_ID,
        "objective": "Run bounded runtime health.",
        "evidence_refs": [],
        "authority_ceiling": "read_only",
        "allowed_capability_profile": ["runtime_health"],
        "resource_budget": {
            "model_calls": 1,
            "local_mcp_calls": 1,
            "wall_seconds": 30,
        },
        "deadline": now + 60,
        "expected_result_schema": delegate.RECEIPT_SCHEMA,
        "return_route": "stdout",
        "requested_action": {
            "tool": "runtime_health",
            "arguments": {},
        },
        "delegation_depth": 0,
    }


class ContinuityAgentLedgerSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_state = delegate.STATE
        delegate.STATE = Path(self.tmp.name)

    def tearDown(self) -> None:
        delegate.STATE = self.old_state
        self.tmp.cleanup()

    def test_ledger_session_precedes_model_and_tool_execution(self):
        events = []

        def open_session(task_id, *, timeout):
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 30.0)
            events.append(("ledger", task_id))
            return "session:continuity-test", "2026-10-04T18:31:44Z"

        def resolve_model():
            events.append(("model", None))
            return "model:test"

        def model_claim(env, validated, model_id, timeout):
            events.append(("claim", validated["tool"]))
            return (
                {
                    "task_id": validated["task_id"],
                    "decision": "CLAIM",
                    "capability": validated["tool"],
                },
                3,
            )

        def local_mcp(tool, arguments, timeout):
            events.append(("mcp", tool))
            return {"isError": False, "content": [{"type": "text", "text": "ok"}]}, 4

        with (
            patch.object(delegate.time, "time", return_value=2_000_000_000),
            patch.object(delegate, "open_ledger_session", side_effect=open_session),
            patch.object(delegate, "resolve_claim_model", side_effect=resolve_model),
            patch.object(delegate, "claim_task", side_effect=model_claim),
            patch.object(delegate, "call_local_mcp", side_effect=local_mcp),
        ):
            receipt = delegate.run(envelope())

        self.assertEqual(receipt["completion_state"], "COMPLETED")
        self.assertEqual(
            [name for name, _ in events],
            ["ledger", "model", "claim", "mcp"],
        )
        self.assertEqual(receipt["resource_usage"]["ledger_calls"], 2)
        self.assertIn(
            "ledger_session:session:continuity-test",
            receipt["evidence_refs"],
        )
        self.assertIn(
            "ledger_session_heartbeat:2026-10-04T18:31:44Z",
            receipt["evidence_refs"],
        )
        self.assertTrue(
            any(
                ref.startswith("claim_sha256:")
                for ref in receipt["evidence_refs"]
            )
        )

    def test_ledger_session_failure_blocks_before_model_or_tool(self):
        with (
            patch.object(delegate.time, "time", return_value=2_000_000_000),
            patch.object(
                delegate,
                "open_ledger_session",
                side_effect=delegate.Reject(
                    "ledger_session_unavailable",
                    "BLOCKED",
                ),
            ),
            patch.object(delegate, "resolve_claim_model") as model,
            patch.object(delegate, "claim_task") as claim,
            patch.object(delegate, "call_local_mcp") as mcp,
        ):
            receipt = delegate.run(envelope("ledger-session-fail-0001"))

        self.assertEqual(receipt["completion_state"], "BLOCKED")
        self.assertEqual(
            receipt["unresolved"],
            ["ledger_session_unavailable"],
        )
        self.assertEqual(receipt["resource_usage"]["ledger_calls"], 0)
        model.assert_not_called()
        claim.assert_not_called()
        mcp.assert_not_called()

    def test_claim_model_uses_receiver_identity_not_ui_preset(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {"models": [{"name": delegate.CLAIM_MODEL_ID}]}
                ).encode("utf-8")

        with patch.object(
            delegate.urllib.request,
            "urlopen",
            return_value=Response(),
        ):
            self.assertEqual(
                delegate.resolve_claim_model(),
                delegate.CLAIM_MODEL_ID,
            )

    def test_missing_accepted_claim_model_fails_closed(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"models":[{"name":"other:model"}]}'

        with patch.object(
            delegate.urllib.request,
            "urlopen",
            return_value=Response(),
        ):
            with self.assertRaises(delegate.Reject) as caught:
                delegate.resolve_claim_model()
        self.assertEqual(
            caught.exception.code,
            "continuity_agent_base_unavailable",
        )
        self.assertEqual(caught.exception.completion_state, "BLOCKED")

    def test_same_task_has_stable_ledger_session_key(self):
        first = delegate._ledger_task_key("task:stable")
        second = delegate._ledger_task_key("task:stable")
        other = delegate._ledger_task_key("task:other")
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 24)


if __name__ == "__main__":
    unittest.main()
