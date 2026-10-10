import json
import unittest

from receipt_record import build_record


class ReceiptRecordTests(unittest.TestCase):
    def setUp(self):
        self.task_id = "chatgpt-cg-20261003-test-01"
        self.secret_text = "PRIVATE_SENTINEL_should_not_be_published"
        self.receipt = {
            "task_id": self.task_id,
            "completion_state": "COMPLETED",
            "executor_identity": {
                "runtime_id": "fasthost.powerpc",
                "uid": 2257347,
                "user": "private-user",
                "hostname": "private-host",
            },
            "actions": [{"capability": "read_text", "arguments_sha256": "abc"}],
            "evidence_refs": ["private://evidence"],
            "resource_usage": {"local_mcp_calls": 1, "transport": "private-route"},
            "runtime_receipt": {"webapp": "/private/path"},
            "result": {
                "content": [{"type": "text", "text": self.secret_text}],
                "isError": False,
            },
            "unresolved": [],
        }
        self.encrypted = {
            "protocol": "powerpc-control-v1",
            "task_id": self.task_id,
            "kind": "result",
            "ciphertext_b64": "opaque-ciphertext",
        }

    def build(self, visibility="summary"):
        return build_record(
            self.receipt,
            self.encrypted,
            task_id=self.task_id,
            fingerprint="SHA256:pinned",
            request_id="cg-20261003-test-01",
            tool="read_text",
            authority="read_only",
            visibility=visibility,
            verified_at=1791000000,
        )

    def test_summary_omits_plaintext_and_host_values_but_keeps_digest(self):
        record = self.build()
        serialized = json.dumps(record, sort_keys=True)
        self.assertNotIn(self.secret_text, serialized)
        self.assertNotIn("private-host", serialized)
        self.assertNotIn("/private/path", serialized)
        self.assertNotIn("private://evidence", serialized)
        summary = record["verified_receipt_summary"]
        self.assertEqual(summary["result_summary"]["text_bytes"], len(self.secret_text))
        self.assertEqual(summary["unresolved_count"], 0)
        self.assertEqual(record["encrypted_result"]["envelope"], self.encrypted)

    def test_public_plaintext_mode_is_rejected_to_prevent_secret_disclosure(self):
        with self.assertRaises(ValueError):
            self.build("public_plaintext")

    def test_task_mismatch_fails_closed(self):
        bad = dict(self.receipt, task_id="wrong-task")
        with self.assertRaises(ValueError):
            build_record(
                bad,
                self.encrypted,
                task_id=self.task_id,
                fingerprint="SHA256:pinned",
                request_id="cg-20261003-test-01",
                tool="read_text",
                authority="read_only",
            )

    def test_unknown_visibility_fails_closed(self):
        with self.assertRaises(ValueError):
            self.build("unredacted")


if __name__ == "__main__":
    unittest.main()
