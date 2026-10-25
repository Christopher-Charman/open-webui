"""Durable occurrence reservation for an existing owned scheduler.

This module does not create a scheduler or execute effects. The existing
scheduler registers deterministic occurrence IDs and claims them through this
owner-pinned SQLite store. Claim expiration produces UNKNOWN, never a replay
permit: the owning dispatcher must independently reconcile the destination.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path


class OccurrenceLedger:
    def __init__(self, database: str | Path):
        self.database = str(database)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS owner_occurrences (
                occurrence_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                due_at INTEGER NOT NULL,
                state TEXT NOT NULL CHECK(state IN
                  ('PENDING','CLAIMED','UNKNOWN','COMPLETE')),
                generation INTEGER NOT NULL DEFAULT 0,
                owner_id TEXT,
                lease_until INTEGER,
                receipt_ref TEXT
            )""")

    def _connect(self):
        db = sqlite3.connect(self.database, timeout=30, isolation_level=None)
        db.execute("PRAGMA busy_timeout=30000")
        return db

    @staticmethod
    def _token(value):
        if not isinstance(value, str) or not value or len(value) > 256:
            raise ValueError("INVALID_OWNER_TOKEN")
        return value

    def register(self, occurrence_id: str, task_id: str, due_at: int):
        self._token(occurrence_id)
        self._token(task_id)
        if type(due_at) is not int or due_at < 0:
            raise ValueError("INVALID_DUE_AT")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT OR IGNORE INTO owner_occurrences "
                "(occurrence_id,task_id,due_at,state) VALUES (?,?,?,'PENDING')",
                (occurrence_id, task_id, due_at))
            row = db.execute(
                "SELECT task_id,due_at,state,generation FROM owner_occurrences "
                "WHERE occurrence_id=?", (occurrence_id,)).fetchone()
            db.commit()
        if row[:2] != (task_id, due_at):
            raise ValueError("OCCURRENCE_ID_CONFLICT")
        return {"state": row[2], "generation": row[3]}

    def claim(self, occurrence_id: str, owner_id: str, now: int,
              lease_seconds: int = 300):
        self._token(occurrence_id)
        self._token(owner_id)
        if (type(now) is not int or type(lease_seconds) is not int
                or not 1 <= lease_seconds <= 86400):
            raise ValueError("INVALID_LEASE")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state,due_at,generation,lease_until FROM owner_occurrences "
                "WHERE occurrence_id=?", (occurrence_id,)).fetchone()
            if row is None:
                result = {"state": "NOT_FOUND"}
            elif row[0] == "CLAIMED" and row[3] <= now:
                db.execute("UPDATE owner_occurrences SET state='UNKNOWN' "
                           "WHERE occurrence_id=? AND state='CLAIMED'",
                           (occurrence_id,))
                result = {"state": "UNKNOWN", "requires_readback": True}
            elif row[0] != "PENDING" or row[1] > now:
                result = {"state": row[0], "claimed": False}
            else:
                generation = row[2] + 1
                db.execute("UPDATE owner_occurrences SET state='CLAIMED',"
                           "generation=?,owner_id=?,lease_until=? "
                           "WHERE occurrence_id=? AND state='PENDING'",
                           (generation, owner_id, now + lease_seconds, occurrence_id))
                result = {"state": "CLAIMED", "generation": generation,
                          "lease_until": now + lease_seconds, "claimed": True}
            db.commit()
        return result

    def complete(self, occurrence_id: str, owner_id: str, generation: int,
                 receipt_ref: str, now: int):
        self._token(occurrence_id)
        self._token(owner_id)
        self._token(receipt_ref)
        if type(generation) is not int or generation < 1 or type(now) is not int:
            raise ValueError("INVALID_GENERATION")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE owner_occurrences SET state='UNKNOWN' "
                       "WHERE occurrence_id=? AND state='CLAIMED' AND lease_until<=?",
                       (occurrence_id, now))
            updated = db.execute(
                "UPDATE owner_occurrences SET state='COMPLETE',receipt_ref=? "
                "WHERE occurrence_id=? AND state='CLAIMED' AND owner_id=? "
                "AND generation=? AND lease_until>?",
                (receipt_ref, occurrence_id, owner_id, generation, now)).rowcount
            db.commit()
        return {"state": "COMPLETE" if updated else "NOT_ACCEPTED",
                "completed": updated == 1}

    def reconcile(self, occurrence_id: str, receipt_ref: str, verify_readback):
        """Only an independently verified destination receipt may complete UNKNOWN.

        The caller is responsible for verifying that receipt before invoking.
        This operation cannot grant a new execution claim.
        """
        self._token(occurrence_id)
        self._token(receipt_ref)
        if not callable(verify_readback):
            raise ValueError("OWNER_READBACK_REQUIRED")
        try:
            verified = verify_readback(occurrence_id, receipt_ref)
        except Exception:
            verified = False
        if verified is not True:
            return {"state": "UNVERIFIED", "changed": False}
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE owner_occurrences SET state='COMPLETE',receipt_ref=? "
                "WHERE occurrence_id=? AND state='UNKNOWN'",
                (receipt_ref, occurrence_id)).rowcount
            db.commit()
        return {"state": "COMPLETE" if changed else "NOT_ACCEPTED",
                "changed": bool(changed)}

    def inspect(self, occurrence_id: str):
        self._token(occurrence_id)
        with self._connect() as db:
            row = db.execute("SELECT state,generation,owner_id,lease_until,"
                             "receipt_ref FROM owner_occurrences "
                             "WHERE occurrence_id=?", (occurrence_id,)).fetchone()
        if row is None:
            return {"state": "NOT_FOUND"}
        return dict(zip(("state","generation","owner_id",
                         "lease_until","receipt_ref"),row))
