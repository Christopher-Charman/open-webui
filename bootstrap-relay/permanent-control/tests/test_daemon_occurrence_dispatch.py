"""Exercise owner queue occurrence binding and published-result recovery."""

import importlib.util
import os
from pathlib import Path
import sqlite3
import time
from unittest.mock import patch

import pytest

from owned_occurrence_ledger import OccurrenceLedger

SCRIPT = Path(__file__).resolve().parents[1] / "daemon.py"
_previous = os.environ.get("PPC_CONTROL_ACCOUNT")
os.environ["PPC_CONTROL_ACCOUNT"] = str(Path(__file__).parent)
spec = importlib.util.spec_from_file_location("owned_daemon_occurrence_test", SCRIPT)
daemon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daemon)
if _previous is None:
    del os.environ["PPC_CONTROL_ACCOUNT"]
else:
    os.environ["PPC_CONTROL_ACCOUNT"] = _previous


def task(suffix, due_at=None):
    now = int(time.time())
    return {
        "protocol": daemon.PROTOCOL,
        "version": daemon.VERSION,
        "task_id": "hermes-occurrence-" + suffix,
        "target_runtime_id": daemon.RUNTIME_ID,
        "created_at": now,
        "expires_at": now + 600,
        "occurrence_id": "hermes-occurrence-" + suffix,
        "due_at": now if due_at is None else due_at,
        "origin_ephemeral_x25519_spki_b64": "dummy",
        "nonce_b64": "dummy",
        "ciphertext_b64": "dummy",
    }


def connection():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE tasks(
        task_id TEXT PRIMARY KEY, envelope_sha256 TEXT NOT NULL,
        state TEXT NOT NULL, received_at INTEGER NOT NULL,
        completed_at INTEGER, result_path TEXT)""")
    return conn


def payload(task):
    return {
        "task_id": task["task_id"],
        "target_runtime_id": daemon.RUNTIME_ID,
        "tool": "runtime_health",
        "allowed_capability_profile": ["runtime_health"],
        "authority_ceiling": "read_only",
        "arguments": {},
    }


def fake_result_io():
    saved = {}

    def publish(_task, _shared, _spriv, receipt):
        saved["receipt"] = receipt
        return "/private/results/" + receipt["task_id"] + ".json"

    def readback(task, _xpriv, _spriv):
        receipt = saved.get("receipt")
        if receipt is None:
            return None
        path = "/private/results/" + task["task_id"] + ".json"
        return {"path": path, "receipt_ref": path + "#sha256=verified",
                "receipt": receipt}

    return publish, readback


def test_due_occurrence_dispatches_once_and_completes_after_readback(tmp_path):
    item = task("complete")
    result = payload(item)
    conn = connection()
    ledger = OccurrenceLedger(tmp_path / "occurrences.sqlite3")
    calls = []
    publish, readback = fake_result_io()
    with (
        patch.object(daemon, "_decrypt_task", return_value=(result, b"secret")),
        patch.object(daemon, "_call_local_mcp", side_effect=lambda tool, args:
                     calls.append(tool) or {"isError": False, "health": "ready"}),
        patch.object(daemon, "_publish_result", side_effect=publish),
        patch.object(daemon, "_readback_published_result", side_effect=readback),
    ):
        daemon._process_task(item, None, None, conn, ledger)
        daemon._process_task(item, None, None, conn, ledger)

    assert calls == ["runtime_health"]
    assert ledger.inspect(item["occurrence_id"])["state"] == "COMPLETE"
    assert conn.execute("select state from tasks where task_id=?",
                        (item["task_id"],)).fetchone() == ("completed",)
    conn.close()


def test_future_occurrence_is_registered_and_waits_for_its_due_time(tmp_path):
    now = int(time.time())
    item = task("future", due_at=now + 120)
    result = payload(item)
    conn = connection()
    ledger = OccurrenceLedger(tmp_path / "occurrences.sqlite3")
    calls = []
    with patch.object(daemon, "_decrypt_task", return_value=(result, b"secret")):
        daemon._process_task(item, None, None, conn, ledger)

    assert calls == []
    assert ledger.inspect(item["occurrence_id"])["state"] == "PENDING"
    assert conn.execute("select count(*) from tasks").fetchone() == (0,)
    conn.close()


def test_unknown_result_is_not_replayed_before_reconciliation(tmp_path):
    item = task("unknown")
    result = payload(item)
    conn = connection()
    ledger = OccurrenceLedger(tmp_path / "occurrences.sqlite3")
    calls = []
    publish, _ = fake_result_io()
    with (
        patch.object(daemon, "_decrypt_task", return_value=(result, b"secret")),
        patch.object(daemon, "_call_local_mcp", side_effect=lambda tool, args:
                     calls.append(tool) or {"isError": False}),
        patch.object(daemon, "_publish_result", side_effect=publish),
        patch.object(daemon, "_readback_published_result", return_value=None),
    ):
        daemon._process_task(item, None, None, conn, ledger)
        daemon._process_task(item, None, None, conn, ledger)

    assert calls == ["runtime_health"]
    assert ledger.inspect(item["occurrence_id"])["state"] == "CLAIMED"
    assert conn.execute("select state from tasks where task_id=?",
                        (item["task_id"],)).fetchone() == ("claimed",)
    conn.close()
