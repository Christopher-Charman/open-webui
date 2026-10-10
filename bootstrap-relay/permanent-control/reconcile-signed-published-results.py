#!/usr/bin/env python3
"""Reconcile signed, published but DB-claimed results without inventing success.

Read-only by default. With --apply, CAS-transition only signed/mirrored
published-result metadata to 'published_outcome_unverified'; no decrypt, no
new task execution, no completion-state inference and no secret disclosure.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

# Deploys as the owning Unix user; never publish host-specific home paths,
# numeric user IDs or confidential state in the public source repository.
ACCOUNT = Path(os.environ.get("PPC_CONTROL_ACCOUNT", str(Path.home().parent)))
EXPECTED_UID = ACCOUNT.stat().st_uid
EXPECTED_RUNTIME = "fasthost.powerpc"
FINGERPRINT = "SHA256:l7SrivQiY5uhxagCB/L9SR7IvXH3EKcP33HdEgeBaRI"
DB = ACCOUNT/".powerpc-control-v1/state.sqlite3"
IDENTITY = ACCOUNT/"htdocs/.well-known/powerpc-control-v1/identity.json"
RESULTS = ACCOUNT/"htdocs/.well-known/powerpc-control-v1/results"
MIRROR = (ACCOUNT/"webapp/envs/openwebui/lib/python3.11/"
          "site-packages/open_webui/static/powerpc-control-v1/results")
EVIDENCE_DIR = ACCOUNT/".powerpc-control-v1/reconciliation-evidence"
UNVERIFIED = "published_outcome_unverified"


def b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def canonical(value: Any) -> bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()


@dataclass(frozen=True)
class Evidence:
    task_id: str
    content_sha256: str
    published_at: int
    result_path: str
    status: str
    reason: str


def load_pinned_public_key(identity_file: Path = IDENTITY) -> ed25519.Ed25519PublicKey:
    from cryptography.hazmat.primitives import hashes
    identity = json.loads(identity_file.read_text(encoding="utf-8"))
    if identity.get("protocol")!="powerpc-control-v1" or identity.get("version")!=1:
        raise ValueError("identity_contract_mismatch")
    if identity.get("runtime_id")!=EXPECTED_RUNTIME:
        raise ValueError("identity_runtime_mismatch")
    ed_der=b64d(identity["ed25519_spki_b64"])
    x_der=b64d(identity["x25519_spki_b64"])
    fingerprint="SHA256:"+base64.b64encode(hashlib.sha256(x_der+ed_der).digest()).decode().rstrip("=")
    if fingerprint!=FINGERPRINT:
        raise ValueError("runtime_identity_pin_mismatch")
    pub=serialization.load_der_public_key(ed_der)
    if not isinstance(pub,ed25519.Ed25519PublicKey):
        raise ValueError("identity_key_not_ed25519")
    if identity.get("identity_fingerprint")!=fingerprint:
        raise ValueError("identity_fingerprint_mismatch")
    signature=b64d(identity["signature_b64"])
    signed=dict(identity)
    signed.pop("signature_b64",None)
    pub.verify(signature,canonical(signed))
    return pub


def attest_published_result(task_id: str, received_at: int,
                            public_key: ed25519.Ed25519PublicKey,
                            results: Path = RESULTS, mirror: Path = MIRROR) -> Evidence:
    primary=results/(task_id+".json")
    duplicate=mirror/(task_id+".json")
    if not primary.is_file() or not duplicate.is_file():
        return Evidence(task_id,"",0,str(primary),"UNRESOLVED","result_or_mirror_missing")
    try:
        if primary.stat().st_size>200000 or duplicate.stat().st_size>200000:
            raise ValueError("oversized_signed_envelope")
        data=primary.read_bytes()
        if data != duplicate.read_bytes():
            raise ValueError("mirror_result_mismatch")
        env=json.loads(data)
        if (not isinstance(env,dict) or env.get("protocol")!="powerpc-control-v1"
            or env.get("version")!=1 or env.get("target_runtime_id")!=EXPECTED_RUNTIME
            or env.get("task_id")!=task_id or env.get("kind")!="result"):
            raise ValueError("result_envelope_binding_invalid")
        sig=b64d(env["signature_b64"])
        signed=dict(env)
        signed.pop("signature_b64")
        public_key.verify(sig,canonical(signed))
        published=env.get("published_at")
        if type(published) is not int or published<received_at-120:
            raise ValueError("result_publication_clock_invalid")
        return Evidence(task_id,hashlib.sha256(data).hexdigest(),published,
                        str(primary),"SIGNED_PUBLISHED","decrypted_outcome_not_verified")
    except Exception as exc:
        return Evidence(task_id,"",0,str(primary),"UNRESOLVED",type(exc).__name__)


def checked_connection(db: Path=DB) -> sqlite3.Connection:
    c=sqlite3.connect(db,timeout=5)
    c.execute("PRAGMA busy_timeout=5000")
    if c.execute("PRAGMA quick_check").fetchone()[0]!="ok":
        c.close()
        raise ValueError("database_integrity_unverified")
    return c


def reconcile_one(conn: sqlite3.Connection,evidence: Evidence,
                  expected_sha: str, apply: bool=False) -> str:
    row=conn.execute(
        "SELECT state,completed_at,result_path,envelope_sha256 FROM tasks WHERE task_id=?",
        (evidence.task_id,),
    ).fetchone()
    if row is None:
        return "UNRESOLVED_MISSING_TASK"
    if row[3]!=expected_sha:
        return "UNRESOLVED_ENVELOPE_CHANGED"
    if row[0]==UNVERIFIED and row[1] is None and row[2]==evidence.result_path:
        return "ALREADY_CLASSIFIED"
    if row[0]!="claimed" or row[1] is not None or row[2] is not None:
        return "UNRESOLVED_STATE_CHANGED"
    if evidence.status!="SIGNED_PUBLISHED":
        return "UNRESOLVED_RESULT_UNVERIFIED"
    if not apply:
        return "ELIGIBLE_NO_MUTATION"
    try:
        cur=conn.execute(
            "UPDATE tasks SET state=?,result_path=? "
            "WHERE task_id=? AND state='claimed' AND completed_at IS NULL "
            "AND result_path IS NULL AND envelope_sha256=?",
            (UNVERIFIED,evidence.result_path,evidence.task_id,expected_sha),
        )
        if cur.rowcount!=1:
            conn.rollback()
            return "UNRESOLVED_CAS_CONFLICT"
        conn.commit()
        verify=conn.execute(
            "SELECT state,completed_at,result_path FROM tasks WHERE task_id=?",
            (evidence.task_id,),
        ).fetchone()
        return ("CLASSIFIED_PUBLISHED_OUTCOME_UNVERIFIED"
                if verify==(UNVERIFIED,None,evidence.result_path)
                else "UNRESOLVED_POST_WRITE_READBACK")
    except sqlite3.Error:
        conn.rollback()
        return "UNRESOLVED_SQLITE_ERROR"


def run(apply: bool=False,db: Path=DB,identity_file: Path=IDENTITY,
        results: Path=RESULTS,mirror: Path=MIRROR,
        evidence_dir: Path=EVIDENCE_DIR,
        expected_task_ids: frozenset[str] | None=None) -> dict[str,Any]:
    if os.getuid()!=EXPECTED_UID:
        raise ValueError("runtime_uid_mismatch")
    if not db.is_file() or db.is_symlink():
        raise ValueError("owned_database_unavailable")
    st=db.stat()
    if st.st_uid!=EXPECTED_UID or stat.S_IMODE(st.st_mode)&0o077:
        raise ValueError("owned_database_owner_or_mode_invalid")
    public=load_pinned_public_key(identity_file)
    if apply:
        if not expected_task_ids or not isinstance(expected_task_ids,frozenset):
            raise ValueError("explicit_exact_claimed_task_set_required")
        if any(not isinstance(x,str) for x in expected_task_ids):
            raise ValueError("invalid_expected_task_id")
        evidence_dir.mkdir(parents=True,mode=0o700,exist_ok=True)
        if stat.S_IMODE(evidence_dir.stat().st_mode)!=0o700:
            raise ValueError("private_evidence_dir_permissions_invalid")
        if (evidence_dir/"published-orphan-reconciliation-20261010.json").exists():
            raise ValueError("private_reconciliation_receipt_already_exists")
    entries=[]
    with checked_connection(db) as conn:
        rows=conn.execute(
            "SELECT task_id,received_at,envelope_sha256 FROM tasks "
            "WHERE state=? ORDER BY task_id",("claimed",),
        ).fetchall()
        if apply and {t[0] for t in rows} != expected_task_ids:
            raise ValueError("claimed_task_set_changed_no_write")
        for tid,received,sha in rows:
            attestation=attest_published_result(tid,received,public,results,mirror)
            result=reconcile_one(conn,attestation,sha,apply=apply)
            entries.append({
                "task_id":tid,"attestation":attestation.status,
                "encrypted_envelope_sha256":attestation.content_sha256,
                "published_at":attestation.published_at,
                "classification":result,"decrypted_outcome_known":False,
            })
    receipt={
        "schema_version":1,
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "mode":"METADATA_CAS" if apply else "READ_ONLY_AUDIT",
        "runtime_id":EXPECTED_RUNTIME,
        "identity_fingerprint":FINGERPRINT,
        "claimed_rows_observed":len(rows),
        "entries":entries,
        "no_effects_dispatched":True,
        "no_decrypted_completion_inferred":True,
        "global_idle_verified":False,
    }
    if apply:
        name="published-orphan-reconciliation-20261010.json"
        output=evidence_dir/name
        if output.exists():
            raise ValueError("private_reconciliation_receipt_already_exists")
        fd=os.open(output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"w") as stream:
            json.dump(receipt,stream,sort_keys=True,indent=2)
            stream.write("\n");stream.flush();os.fsync(stream.fileno())
    return receipt


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--task-id",action="append",default=[])
    args=parser.parse_args()
    try:
        if args.apply and (not args.task_id or len(args.task_id)!=len(set(args.task_id))):
            raise ValueError("explicit_unique_task_ids_required")
        report=run(apply=args.apply,
                   expected_task_ids=frozenset(args.task_id) if args.apply else None)
        # Emit only task IDs and verification classes; keep signed payload private.
        print(json.dumps(report,sort_keys=True))
        if any(x["classification"].startswith("UNRESOLVED") for x in report["entries"]):
            return 2
        return 0
    except (ValueError,sqlite3.Error,OSError) as exc:
        print(json.dumps({"state":"BLOCKED","reason":type(exc).__name__}))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
