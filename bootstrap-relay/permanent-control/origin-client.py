#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
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

PROTOCOL = "powerpc-control-v1"
VERSION = 1
RUNTIME_ID = "fasthost.powerpc"
ALLOWED_TOOLS = {"runtime_health", "read_text", "list_dir", "terminal_exec"}


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
        info=b"powerpc-control-v1/" + purpose,
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


def validate_identity(identity: dict[str, Any]) -> tuple[x25519.X25519PublicKey, ed25519.Ed25519PublicKey]:
    if identity.get("protocol") != PROTOCOL or identity.get("version") != VERSION:
        raise ValueError("identity protocol/version mismatch")
    if identity.get("runtime_id") != RUNTIME_ID:
        raise ValueError("identity runtime mismatch")
    xpub = serialization.load_der_public_key(b64d(identity["x25519_spki_b64"]))
    epub = serialization.load_der_public_key(b64d(identity["ed25519_spki_b64"]))
    if not isinstance(xpub, x25519.X25519PublicKey):
        raise ValueError("identity x25519 key invalid")
    if not isinstance(epub, ed25519.Ed25519PublicKey):
        raise ValueError("identity ed25519 key invalid")

    sig_text = identity.get("signature_b64")
    if sig_text:
        signed = dict(identity)
        signed.pop("signature_b64", None)
        epub.verify(b64d(sig_text), canon(signed))
    return xpub, epub


def prepare(args: argparse.Namespace) -> int:
    identity = load_json(args.identity)
    xpub, epub = validate_identity(identity)

    tool = args.tool
    if tool not in ALLOWED_TOOLS:
        raise ValueError("tool is outside the PowerPC bounded contract")
    if args.authority == "read_only" and tool == "terminal_exec":
        raise ValueError("read_only authority cannot request terminal_exec")

    arguments = json.loads(args.arguments)
    if not isinstance(arguments, dict):
        raise ValueError("--arguments must decode to an object")

    task_id = args.task_id or ("ppc-" + uuid.uuid4().hex)
    now = int(time.time())
    ttl = int(args.ttl)
    if ttl < 1 or ttl > 3600:
        raise ValueError("ttl must be 1..3600 seconds")

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
        "created_at": now,
        "expires_at": now + ttl,
        "origin_ephemeral_x25519_spki_b64": b64e(origin_pub_der),
    }
    aad = canon(task)
    payload = {
        "task_id": task_id,
        "target_runtime_id": RUNTIME_ID,
        "tool": tool,
        "arguments": arguments,
        "authority_ceiling": args.authority,
        "allowed_capability_profile": [tool],
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
        "created_at": now,
        "expires_at": now + ttl,
    }

    out = Path(args.output)
    ctx = Path(args.context)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(canon(task) + b"\n")
    atomic_private(ctx, canon(context) + b"\n")
    print(f"TASK_PREPARED={task_id}")
    print(f"TASK_JSON={out}")
    print(f"CONTEXT_PRIVATE={ctx}")
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
    p = argparse.ArgumentParser(description="Origin-side encoder/verifier for powerpc-control-v1")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("prepare")
    a.add_argument("--identity", required=True, help="runtime identity.json")
    a.add_argument("--tool", required=True, choices=sorted(ALLOWED_TOOLS))
    a.add_argument("--arguments", default="{}")
    a.add_argument("--authority", choices=["read_only", "bounded_operator"], default="read_only")
    a.add_argument("--ttl", type=int, default=600)
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
