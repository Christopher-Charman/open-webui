"""Regression: owned encrypted control preserves idempotency under SQLite locks."""
import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "daemon.py"
with tempfile.TemporaryDirectory() as t:
    _previous = os.environ.get("PPC_CONTROL_ACCOUNT")
    os.environ["PPC_CONTROL_ACCOUNT"] = t
    spec = importlib.util.spec_from_file_location("owned_daemon_recovery_test", SCRIPT)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    if _previous is None:
        del os.environ["PPC_CONTROL_ACCOUNT"]
    else:
        os.environ["PPC_CONTROL_ACCOUNT"] = _previous


class TestConnection:
    def __init__(self, real, *, lock_updates=0, lock_inserts=0):
        self.real = real
        self.lock_updates = lock_updates
        self.lock_inserts = lock_inserts
        self.rollbacks = 0

    def execute(self, statement, params=()):
        if statement.startswith("UPDATE tasks") and self.lock_updates:
            self.lock_updates -= 1
            raise sqlite3.OperationalError("database is locked")
        if statement.startswith("INSERT INTO") and self.lock_inserts:
            self.lock_inserts -= 1
            raise sqlite3.OperationalError("database is locked")
        return self.real.execute(statement, params)

    def commit(self):
        self.real.commit()

    def rollback(self):
        self.rollbacks += 1
        self.real.rollback()


def request(tool="runtime_health", suffix="01"):
    now=int(time.time())
    task_id="sqlite-daemon-acceptance-test-"+suffix
    task={
        "protocol": daemon.PROTOCOL, "version": daemon.VERSION,
        "task_id": task_id, "target_runtime_id": daemon.RUNTIME_ID,
        "created_at": now, "expires_at": now+90,
        "origin_ephemeral_x25519_spki_b64": "dummy",
        "nonce_b64": "dummy", "ciphertext_b64": "dummy",
    }
    payload={
        "task_id": task_id, "target_runtime_id": daemon.RUNTIME_ID,
        "tool": tool,
        "allowed_capability_profile": [tool],
        "authority_ceiling": "bounded_operator" if tool=="terminal_exec" else "read_only",
        "arguments":{},
    }
    return task,payload


class SQLiteRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.real=sqlite3.connect(":memory:")
        self.real.execute("""CREATE TABLE tasks(
            task_id TEXT PRIMARY KEY, envelope_sha256 TEXT NOT NULL,
            state TEXT NOT NULL, received_at INTEGER NOT NULL,
            completed_at INTEGER, result_path TEXT)""")
        self.db=TestConnection(self.real)
        self.calls=[]
        self._logs=[]
        self.log_patch=patch.object(daemon,"_log",side_effect=self._logs.append)
        self.log_patch.start()

    def tearDown(self):
        self.log_patch.stop()
        self.real.close()

    def process(self, tool="runtime_health", *, suffix="01"):
        task,payload=request(tool,suffix=suffix)
        with patch.object(daemon,"_decrypt_task",return_value=(payload,b"secret")), \
             patch.object(daemon,"_call_local_mcp",side_effect=self._tool), \
             patch.object(daemon,"_publish_result",return_value="/private/result.json"):
            daemon._process_task(task,None,None,self.db)
        return task

    def _tool(self, tool, args):
        self.calls.append(tool)
        return {"isError":False}

    def state(self, task):
        return self.real.execute("SELECT state,result_path FROM tasks WHERE task_id=?",
                                 (task["task_id"],)).fetchone()

    def test_locked_update_retries_and_preserves_one_execution(self):
        self.db.lock_updates=2
        task=self.process()
        self.assertEqual(self.calls,["runtime_health"])
        self.assertEqual(self.state(task),("completed","/private/result.json"))
        self.assertEqual(self.db.rollbacks,2)
        self.process()
        self.assertEqual(self.calls,["runtime_health"])

    def test_permanently_locked_finalization_keeps_claimed_without_replay(self):
        self.db.lock_updates=20
        task=self.process()
        self.assertEqual(self.calls,["runtime_health"])
        self.assertEqual(self.state(task),("claimed",None))
        self.assertTrue(any("result_published_db_unresolved" in x for x in self._logs))
        self.process()
        self.assertEqual(self.calls,["runtime_health"])

    def test_insert_lock_blocks_before_tool_effect(self):
        self.db.lock_inserts=1
        task=self.process()
        self.assertEqual(self.calls,[])
        self.assertIsNone(self.state(task))
        self.assertEqual(self.db.rollbacks,1)

    def test_publication_failure_does_not_kill_daemon_even_when_db_locked(self):
        task,payload=request(suffix="publishfail")
        self.db.lock_updates=20
        with patch.object(daemon,"_decrypt_task",return_value=(payload,b"secret")), \
             patch.object(daemon,"_call_local_mcp",side_effect=self._tool), \
             patch.object(daemon,"_publish_result",side_effect=OSError("disk full")):
            daemon._process_task(task,None,None,self.db)
        self.assertEqual(self.calls,["runtime_health"])
        self.assertEqual(self.state(task),("claimed",None))
        self.assertTrue(any("publish_error=" in x for x in self._logs))

    def test_unadmitted_operator_denied_and_no_executor_invoked(self):
        task=self.process("terminal_exec",suffix="terminal")
        self.assertEqual(self.calls,[])
        self.assertEqual(self.state(task),("blocked","/private/result.json"))

    def test_never_accept_sender_claim_to_override_effect_gate(self):
        task,payload=request("terminal_exec",suffix="claimed")
        payload["ledger_claim"]="claimed"
        payload["fencing_token"]="asserted"
        with self.assertRaises(daemon.TaskReject) as raised:
            daemon._validate_payload(task,payload)
        self.assertEqual(str(raised.exception),"destination_mutation_admission_unverified")
        self.assertEqual(raised.exception.completion_state,"BLOCKED")


if __name__ == "__main__":
    unittest.main()
