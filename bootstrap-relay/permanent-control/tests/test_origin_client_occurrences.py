"""Origin client binds deterministic occurrence timing into new envelopes."""

import base64
import hashlib
import importlib.util
import json
from argparse import Namespace
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

SOURCE = Path(__file__).resolve().parents[1] / "origin-client.py"
spec = importlib.util.spec_from_file_location("owned_origin_client_occurrence_test", SOURCE)
origin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(origin)


def test_prepare_persists_occurrence_id_and_due_time(tmp_path):
    xpriv = x25519.X25519PrivateKey.generate()
    epriv = ed25519.Ed25519PrivateKey.generate()
    xder = xpriv.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    eder = epriv.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    body = {
        "protocol": origin.PROTOCOL,
        "version": origin.VERSION,
        "runtime_id": origin.RUNTIME_ID,
        "x25519_spki_b64": origin.b64e(xder),
        "ed25519_spki_b64": origin.b64e(eder),
        "identity_fingerprint": "SHA256:" + base64.b64encode(
            hashlib.sha256(xder + eder).digest()).decode("ascii").rstrip("="),
    }
    identity = {**body, "signature_b64": origin.b64e(epriv.sign(origin.canon(body)))}
    identity_path = tmp_path / "identity.json"
    task_path = tmp_path / "task.json"
    context_path = tmp_path / "context.json"
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    now = int(origin.time.time())
    args = Namespace(
        identity=str(identity_path), expected_fingerprint=None,
        tool="runtime_health", negative_contract_test=False,
        authority="read_only", arguments="{}", task_id="scheduled-task-001",
        created_at=now, ttl=600, due_at=now + 30,
        occurrence_id="scheduled-occurrence-001", expires_at=now + 300,
        allowed=None, output=str(task_path), context=str(context_path),
    )

    assert origin.prepare(args) == 0
    task = json.loads(task_path.read_text(encoding="utf-8"))
    context = json.loads(context_path.read_text(encoding="utf-8"))
    assert task["occurrence_id"] == "scheduled-occurrence-001"
    assert task["due_at"] == now + 30
    assert context["occurrence_id"] == task["occurrence_id"]
    assert context["due_at"] == task["due_at"]
