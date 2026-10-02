#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PROTOCOL = "evenio-control-v1"
VERSION = 1
RUNTIME_ID = "fasthost.evenio"
ALLOWED_TOOLS = {"runtime_health", "control_state", "runtime_audit", "delegation_probe"}


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode((text + "=" * (-len(text) % 4)).encode("ascii"))


def canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def atomic_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def derive(shared: bytes, task_id: str, purpose: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=task_id.encode("utf-8"),
        info=b"evenio-control-v1/" + purpose,
    ).derive(shared)


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        obj = json.load(sys.stdin)
    else:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("JSON root must be an object")
    return obj


def validate_identity(
    identity: dict[str, Any],
    expected_fingerprint: str | None = None,
) -> tuple[x25519.X25519PublicKey, ed25519.Ed25519PublicKey, str]:
    if identity.get("protocol") != PROTOCOL or identity.get("version") != VERSION:
        raise ValueError("identity protocol/version mismatch")
    if identity.get("runtime_id") != RUNTIME_ID:
        raise ValueError("identity runtime mismatch")
    xder = b64d(identity["x25519_spki_b64"])
    eder = b64d(identity["ed25519_spki_b64"])
    xpub = serialization.load_der_public_key(xder)
    epub = serialization.load_der_public_key(eder)
    if not isinstance(xpub, x25519.X25519PublicKey):
        raise ValueError("identity x25519 key invalid")
    if not isinstance(epub, ed25519.Ed25519PublicKey):
        raise ValueError("identity ed25519 key invalid")

    sig_text = identity.get("signature_b64")
    if not isinstance(sig_text, str) or not sig_text:
        raise ValueError("identity signature missing")
    signed = dict(identity)
    signed.pop("signature_b64", None)
    epub.verify(b64d(sig_text), canon(signed))

    fingerprint = "SHA256:" + base64.b64encode(
        hashlib.sha256(xder + eder).digest()
    ).decode("ascii").rstrip("=")
    if identity.get("identity_fingerprint") != fingerprint:
        raise ValueError("identity fingerprint mismatch")
    if expected_fingerprint and fingerprint != expected_fingerprint:
        raise ValueError("identity fingerprint pin mismatch")
    return xpub, epub, fingerprint


def prepare(args: argparse.Namespace) -> int:
    identity = load_json(args.identity)
    xpub, epub, fingerprint = validate_identity(identity, args.expected_fingerprint)

    tool = args.tool
    if not args.negative_contract_test:
        if tool not in ALLOWED_TOOLS:
            raise ValueError("tool is outside the Evenio bounded contract")
        if args.authority == "read_only" and tool == "terminal_exec":
            raise ValueError("read_only authority cannot request terminal_exec")

    arguments = json.loads(args.arguments)
    if not isinstance(arguments, dict):
        raise ValueError("--arguments must decode to an object")

    task_id = args.task_id or ("evn-" + uuid.uuid4().hex)
    wall_now = int(time.time())
    created_at = int(args.created_at) if args.created_at is not None else wall_now
    ttl = int(args.ttl)
    if ttl < 1 or ttl > 3600:
        raise ValueError("ttl must be 1..3600 seconds")
    expires_at = int(args.expires_at) if args.expires_at is not None else created_at + ttl

    origin_priv = x25519.X25519PrivateKey.generate()
    origin_pub_der = origin_priv.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    shared = origin_priv.exchange(xpub)

    task = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "task_id": task_id,
        "target_runtime_id": RUNTIME_ID,
        "created_at": created_at,
        "expires_at": expires_at,
        "origin_ephemeral_x25519_spki_b64": b64e(origin_pub_der),
    }
    aad = canon(task)
    allowed = [tool] if args.allowed is None else [x for x in args.allowed.split(",") if x]
    payload = {
        "task_id": task_id,
        "target_runtime_id": RUNTIME_ID,
        "tool": tool,
        "arguments": arguments,
        "authority_ceiling": args.authority,
        "allowed_capability_profile": allowed,
        "expected_result_schema": "assistant-delegation-receipt-v1",
    }
    nonce = os.urandom(12)
    key = derive(shared, task_id, b"command")
    task["nonce_b64"] = b64e(nonce)
    task["ciphertext_b64"] = b64e(AESGCM(key).encrypt(nonce, canon(payload), aad))

    context = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "task_id": task_id,
        "target_runtime_id": RUNTIME_ID,
        "shared_secret_b64": b64e(shared),
        "runtime_ed25519_spki_b64": b64e(
            epub.public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        ),
        "identity_fingerprint": fingerprint,
        "created_at": created_at,
        "expires_at": expires_at,
    }

    out = Path(args.output)
    ctx = Path(args.context)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(canon(task) + b"\n")
    atomic_private(ctx, canon(context) + b"\n")
    print(f"TASK_PREPARED={task_id}")
    print(f"TASK_JSON={out}")
    print(f"CONTEXT_PRIVATE={ctx}")
    print(f"IDENTITY_FINGERPRINT={fingerprint}")
    return 0


def decode(args: argparse.Namespace) -> int:
    result = load_json(args.result)
    context = load_json(args.context)
    task_id = context.get("task_id")

    if result.get("protocol") != PROTOCOL or result.get("version") != VERSION:
        raise ValueError("result protocol/version mismatch")
    if result.get("task_id") != task_id:
        raise ValueError("result task_id mismatch")
    if result.get("target_runtime_id") != RUNTIME_ID:
        raise ValueError("result runtime mismatch")
    if result.get("kind") != "result":
        raise ValueError("result kind mismatch")

    epub = serialization.load_der_public_key(b64d(context["runtime_ed25519_spki_b64"]))
    if not isinstance(epub, ed25519.Ed25519PublicKey):
        raise ValueError("context ed25519 key invalid")

    signed = dict(result)
    sig = b64d(signed.pop("signature_b64"))
    epub.verify(sig, canon(signed))

    aad = canon({
        "protocol": PROTOCOL,
        "version": VERSION,
        "task_id": task_id,
        "target_runtime_id": RUNTIME_ID,
        "kind": "result",
    })
    shared = b64d(context["shared_secret_b64"])
    key = derive(shared, task_id, b"result")
    plaintext = AESGCM(key).decrypt(
        b64d(result["nonce_b64"]),
        b64d(result["ciphertext_b64"]),
        aad,
    )
    receipt = json.loads(plaintext.decode("utf-8"))
    if not isinstance(receipt, dict):
        raise ValueError("decrypted receipt is not an object")

    output = json.dumps(receipt, indent=2, sort_keys=True)
    if args.output == "-":
        print(output)
    else:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(output + "\n", encoding="utf-8")
        print(f"RESULT_VERIFIED={task_id}")
        print(f"RECEIPT_JSON={p}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Origin-side encoder/verifier for evenio-control-v1")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("prepare")
    a.add_argument("--identity", required=True, help="runtime identity.json")
    a.add_argument("--tool", required=True)
    a.add_argument("--arguments", default="{}")
    a.add_argument("--authority", choices=["read_only", "bounded_operator"], default="read_only")
    a.add_argument("--allowed", help="comma-separated capability profile; defaults to requested tool")
    a.add_argument("--ttl", type=int, default=600)
    a.add_argument("--created-at", type=int)
    a.add_argument("--expires-at", type=int)
    a.add_argument("--expected-fingerprint")
    a.add_argument("--negative-contract-test", action="store_true")
    a.add_argument("--task-id")
    a.add_argument("--output", required=True)
    a.add_argument("--context", required=True)
    a.set_defaults(fn=prepare)

    d = sub.add_parser("decode")
    d.add_argument("--result", required=True)
    d.add_argument("--context", required=True)
    d.add_argument("--output", default="-")
    d.set_defaults(fn=decode)

    args = p.parse_args()
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
