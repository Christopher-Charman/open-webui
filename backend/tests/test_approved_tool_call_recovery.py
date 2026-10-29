"""Focused regressions for approved tool-call claim fencing and recovery."""

import os
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("WEBUI_SECRET_KEY", "test-only-not-for-authentication")
os.environ.setdefault("DATA_DIR", str(Path(__file__).resolve().parents[1] / "data"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from open_webui.models.chats import Chat, Chats


CHAT_ID = "chat-test"
MESSAGE_ID = "message-test"
CALL_ID = "call-test"


def make_chat(call):
    return Chat(
        id=CHAT_ID,
        user_id="user-test",
        title="Test",
        chat={"history": {"messages": {MESSAGE_ID: {
            "id": MESSAGE_ID, "role": "assistant", "output": [dict(call)]
        }}}},
        created_at=1,
        updated_at=1,
    )


class FakeSession:
    def __init__(self, row, dialect):
        self.row = row
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect))
        self.get = AsyncMock(return_value=row)
        self.execute = AsyncMock()
        self.commit = AsyncMock()


class SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_):
        return False


class ApprovedToolCallRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.call = {
            "type": "function_call", "call_id": CALL_ID, "status": "queued",
            "approved": True, "arguments": {"query": "original"},
        }
        self.row = make_chat(self.call)
        self.sessions = []

    def context_for(self, dialect):
        session = FakeSession(self.row, dialect)
        self.sessions.append(session)
        return SessionContext(session)

    def enter_patches(self, dialect="sqlite"):
        from contextlib import ExitStack
        stack = ExitStack()
        replacements = (
            patch("open_webui.models.chats.get_async_db_context",
                  side_effect=lambda: self.context_for(dialect)),
            patch("open_webui.models.chats.flag_modified"),
            patch.object(Chats, "_sanitize_chat_row", lambda _row: None),
            patch.object(Chats, "_repair_chat_current_id", lambda _chat: None),
            patch.object(Chats, "get_current_message_id", lambda _chat: MESSAGE_ID),
            patch("open_webui.models.chats.ChatMessages.upsert_message", new_callable=AsyncMock),
            patch("open_webui.models.chats.time.time", return_value=1000),
            patch("open_webui.models.chats.uuid.uuid4", return_value=SimpleNamespace(hex="claim-1")),
        )
        for replacement in replacements:
            stack.enter_context(replacement)
        self.addCleanup(stack.close)
        return stack

    async def test_claim_uses_dialect_lock_and_mints_claim(self):
        for dialect in ("sqlite", "postgresql"):
            with self.subTest(dialect=dialect), self.enter_patches(dialect):
                result = await Chats.claim_approved_tool_call(CHAT_ID, MESSAGE_ID, CALL_ID)
                self.assertIsNotNone(result)
                call = self.row.chat["history"]["messages"][MESSAGE_ID]["output"][0]
                self.assertEqual(call["status"], "in_progress")
                self.assertEqual(call["execution_claim"], {"id": "claim-1", "claimed_at": 1000})
                session = self.sessions[-1]
                session.commit.assert_awaited_once()
                self.assertEqual(session.get.call_args.kwargs["with_for_update"], dialect == "postgresql")
                if dialect == "sqlite":
                    session.execute.assert_awaited_once()
                else:
                    session.execute.assert_not_awaited()
            self.row = make_chat(self.call)

    async def test_current_claim_completes_once_and_fences_late_worker(self):
        self.call.update(status="in_progress", execution_claim={"id": "claim-1", "claimed_at": 100})
        self.row = make_chat(self.call)
        output = {"type": "function_call_output", "call_id": CALL_ID, "output": "done"}
        with self.enter_patches():
            result = await Chats.finish_approved_tool_call(
                CHAT_ID, MESSAGE_ID, CALL_ID, "claim-1", "completed",
                arguments={"query": "updated"}, output_record=output,
            )
            self.assertIsNotNone(result)
            call = self.row.chat["history"]["messages"][MESSAGE_ID]["output"][0]
            self.assertEqual(call["status"], "completed")
            self.assertEqual(call["arguments"], {"query": "updated"})
            self.assertNotIn("execution_claim", call)
            self.assertEqual(self.row.chat["history"]["messages"][MESSAGE_ID]["output"][1], output)
            successful_session = self.sessions[-1]
            commits_after_success = successful_session.commit.await_count

            late = await Chats.finish_approved_tool_call(
                CHAT_ID, MESSAGE_ID, CALL_ID, "claim-1", "failed",
                output_record={"type": "function_call_output", "call_id": CALL_ID, "output": "late"},
            )
            self.assertIsNone(late)
            self.assertEqual(successful_session.commit.await_count, commits_after_success)
            self.assertEqual(self.sessions[-1].commit.await_count, 0)
            self.assertEqual(len(self.row.chat["history"]["messages"][MESSAGE_ID]["output"]), 2)

    async def test_recovery_requires_expired_exact_claim_and_fences_late_worker(self):
        self.call.update(status="in_progress", execution_claim={"id": "claim-1", "claimed_at": 100})
        self.row = make_chat(self.call)
        output = {"type": "function_call_output", "call_id": CALL_ID, "output": "outcome unknown"}
        with self.enter_patches():
            too_early = await Chats.recover_stale_approved_tool_call(
                CHAT_ID, MESSAGE_ID, CALL_ID, "claim-1", 99, output,
            )
            self.assertIsNone(too_early)
            self.sessions[-1].commit.assert_not_awaited()

            recovered = await Chats.recover_stale_approved_tool_call(
                CHAT_ID, MESSAGE_ID, CALL_ID, "claim-1", 100, output,
            )
            self.assertIsNotNone(recovered)
            call = self.row.chat["history"]["messages"][MESSAGE_ID]["output"][0]
            self.assertEqual(call["status"], "outcome_unknown")
            self.assertNotIn("execution_claim", call)
            self.assertEqual(self.row.chat["history"]["messages"][MESSAGE_ID]["output"][1], output)

            late = await Chats.finish_approved_tool_call(
                CHAT_ID, MESSAGE_ID, CALL_ID, "claim-1", "completed",
                output_record={"type": "function_call_output", "call_id": CALL_ID, "output": "late"},
            )
            self.assertIsNone(late)
            self.assertEqual(len(self.row.chat["history"]["messages"][MESSAGE_ID]["output"]), 2)

    async def test_invalid_output_identity_and_duplicate_result_are_rejected(self):
        self.call.update(status="in_progress", execution_claim={"id": "claim-1", "claimed_at": 100})
        self.row = make_chat(self.call)
        with self.enter_patches():
            wrong_output = await Chats.finish_approved_tool_call(
                CHAT_ID, MESSAGE_ID, CALL_ID, "claim-1", "completed",
                output_record={"type": "function_call_output", "call_id": "different", "output": "bad"},
            )
            self.assertIsNone(wrong_output)
            self.assertEqual(self.sessions[-1].commit.await_count, 0)

            output = {"type": "function_call_output", "call_id": CALL_ID, "output": "done"}
            first = await Chats.finish_approved_tool_call(
                CHAT_ID, MESSAGE_ID, CALL_ID, "claim-1", "completed", output_record=output,
            )
            self.assertIsNotNone(first)
            successful_session = self.sessions[-1]
            second = await Chats.finish_approved_tool_call(
                CHAT_ID, MESSAGE_ID, CALL_ID, "claim-1", "completed", output_record=output,
            )
            self.assertIsNone(second)
            self.assertEqual(successful_session.commit.await_count, 1)
            self.assertEqual(self.sessions[-1].commit.await_count, 0)


if __name__ == "__main__":
    unittest.main()
