#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PROTOCOL = "powerpc-control-v1"
VERSION = 1
RUNTIME_ID = "fasthost.powerpc"
EXPECTED_UID = int(os.environ.get("PPC_CONTROL_EXPECTED_UID", str(os.getuid())))
ACCOUNT = Path(os.environ.get("PPC_CONTROL_ACCOUNT", str(Path.home())))
WEBAPP = Path(os.environ.get("PPC_CONTROL_WEBAPP", str(ACCOUNT / "webapp")))
HTDOCS = Path(os.environ.get("PPC_CONTROL_HTDOCS", str(ACCOUNT / "htdocs")))
STATE = Path(os.environ.get("PPC_CONTROL_STATE", str(ACCOUNT / ".powerpc-control-v1")))
PUBLIC = HTDOCS / ".well-known" / PROTOCOL
RESULTS = PUBLIC / "results"
PUBLIC_MIRROR = Path(os.environ.get(
    "PPC_CONTROL_PUBLIC_MIRROR",
    str(WEBAPP / "envs" / "openwebui" / "lib" / "python3.11" / "site-packages" / "open_webui" / "static" / PROTOCOL),
))
MIRROR_RESULTS = PUBLIC_MIRROR / "results"

def _discover_public_mirrors() -> list[Path]:
    mirrors = {PUBLIC_MIRROR}
    # Keep discovery bounded. WEBAPP is NFS-backed on the hosted runtime, so a
    # recursive "**" scan here can block daemon startup before PID/heartbeat
    # publication. Known environment layouts are sufficient and deterministic.
    patterns = (
        "envs/*/lib/python*/site-packages/open_webui/static/owui-orb-v1.js",
        "miniconda/envs/*/lib/python*/site-packages/open_webui/static/owui-orb-v1.js",
    )
    for pattern in patterns:
        try:
            for marker in WEBAPP.glob(pattern):
                if marker.is_file():
                    mirrors.add(marker.parent)
        except OSError:
            continue
    return sorted(mirrors, key=lambda p: str(p))

PUBLIC_MIRRORS = _discover_public_mirrors()
PIDFILE = STATE / "daemon.pid"
DBFILE = STATE / "state.sqlite3"
LOGFILE = STATE / "daemon.log"
X25519_PRIV = STATE / "x25519-private.pem"
ED25519_PRIV = STATE / "ed25519-private.pem"
HELPER = Path(os.environ.get("PPC_CONTROL_MCP_HELPER", str(STATE / "local-mcp-call.mjs")))
QUEUE_URL = os.environ.get(
    "PPC_CONTROL_QUEUE_URL",
    "https://raw.githubusercontent.com/Christopher-Charman/open-webui/main/bootstrap-relay/permanent-control/queue.json",
)
QUEUE_REFS_URL = os.environ.get(
    "PPC_CONTROL_QUEUE_REFS_URL",
    "https://github.com/Christopher-Charman/open-webui.git/info/refs?service=git-upload-pack",
)
QUEUE_IMMUTABLE_URL_TEMPLATE = os.environ.get(
    "PPC_CONTROL_QUEUE_IMMUTABLE_URL_TEMPLATE",
    "https://raw.githubusercontent.com/Christopher-Charman/open-webui/{sha}/bootstrap-relay/permanent-control/queue.json",
)
QUEUE_API_URL = os.environ.get(
    "PPC_CONTROL_QUEUE_API_URL",
    "https://api.github.com/repos/Christopher-Charman/open-webui/contents/bootstrap-relay/permanent-control/queue.json?ref=main",
)
POLL_SECONDS = float(os.environ.get("PPC_CONTROL_POLL_SECONDS", "7"))
API_FALLBACK_SECONDS = float(os.environ.get("PPC_CONTROL_API_FALLBACK_SECONDS", "75"))
HEARTBEAT_SECONDS = int(os.environ.get("PPC_CONTROL_HEARTBEAT_SECONDS", "30"))
MAX_QUEUE_BYTES = 1024 * 1024
MAX_TASKS = 128
MAX_CLOCK_SKEW = 120
MAX_FUTURE_SECONDS = 3600
MAX_RESULT_PLAINTEXT = 180_000
ALLOWED_TOOLS = {"runtime_health", "read_text", "list_dir", "terminal_exec"}
STOP = False
_LAST_API_FALLBACK_MONO = 0.0

class TaskReject(Exception):
    def __init__(self, message: str, completion_state: str = "FAILED"):
        super().__init__(message)
        self.completion_state = completion_state


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode((text + "=" * (-len(text) % 4)).encode("ascii"))


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _log(msg: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with LOGFILE.open("a", encoding="utf-8") as f:
        f.write(f"{stamp} {msg}\n")
    os.chmod(LOGFILE, 0o600)


def _load_or_create_keys():
    STATE.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    if X25519_PRIV.exists():
        xpriv = serialization.load_pem_private_key(X25519_PRIV.read_bytes(), password=None)
        if not isinstance(xpriv, x25519.X25519PrivateKey):
            raise RuntimeError("invalid persisted X25519 key")
    else:
        xpriv = x25519.X25519PrivateKey.generate()
        _atomic_write(
            X25519_PRIV,
            xpriv.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            0o600,
        )
    if ED25519_PRIV.exists():
        spriv = serialization.load_pem_private_key(ED25519_PRIV.read_bytes(), password=None)
        if not isinstance(spriv, ed25519.Ed25519PrivateKey):
            raise RuntimeError("invalid persisted Ed25519 key")
    else:
        spriv = ed25519.Ed25519PrivateKey.generate()
        _atomic_write(
            ED25519_PRIV,
            spriv.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            0o600,
        )
    return xpriv, spriv


def _spki(pub) -> bytes:
    return pub.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _identity_payload(xpriv, spriv, started_at: int, heartbeat_at: int) -> dict[str, Any]:
    xpub = _spki(xpriv.public_key())
    spub = _spki(spriv.public_key())
    return {
        "protocol": PROTOCOL,
        "version": VERSION,
        "runtime_id": RUNTIME_ID,
        "user": os.environ.get("USER", "unknown"),
        "uid": os.getuid(),
        "hostname": socket.gethostname(),
        "state": "ready",
        "started_at": started_at,
        "heartbeat_at": heartbeat_at,
        "x25519_spki_b64": _b64e(xpub),
        "ed25519_spki_b64": _b64e(spub),
        "identity_fingerprint": "SHA256:" + base64.b64encode(hashlib.sha256(xpub + spub).digest()).decode("ascii").rstrip("="),
        "tool_contract": sorted(ALLOWED_TOOLS),
    }


def _publish_identity(xpriv, spriv, started_at: int) -> None:
    now = int(time.time())
    body = _identity_payload(xpriv, spriv, started_at, now)
    sig = spriv.sign(_canon(body))
    out = dict(body)
    out["signature_b64"] = _b64e(sig)
    identity_bytes = _canon(out) + b"\n"
    _atomic_write(PUBLIC / "identity.json", identity_bytes, 0o644)
    for mirror in PUBLIC_MIRRORS:
        _atomic_write(mirror / "identity.json", identity_bytes, 0o644)
        _atomic_write(mirror / "ppc-control-identity-live.json", identity_bytes, 0o644)
        _atomic_write(mirror / PROTOCOL / "identity.json", identity_bytes, 0o644)
    status = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "runtime_id": RUNTIME_ID,
        "state": "ready",
        "heartbeat_at": now,
        "pid": os.getpid(),
    }
    status["signature_b64"] = _b64e(spriv.sign(_canon(status)))
    status_bytes = _canon(status) + b"\n"
    _atomic_write(PUBLIC / "status.json", status_bytes, 0o644)
    for mirror in PUBLIC_MIRRORS:
        _atomic_write(mirror / "status.json", status_bytes, 0o644)
        _atomic_write(mirror / "ppc-control-status-live.json", status_bytes, 0o644)
        _atomic_write(mirror / PROTOCOL / "status.json", status_bytes, 0o644)


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DBFILE, timeout=5)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks(
            task_id TEXT PRIMARY KEY,
            envelope_sha256 TEXT NOT NULL,
            state TEXT NOT NULL,
            received_at INTEGER NOT NULL,
            completed_at INTEGER,
            result_path TEXT
        )"""
    )
    conn.commit()
    return conn


def _parse_queue_bytes(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_QUEUE_BYTES:
        raise ValueError("queue_too_large")
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("queue_not_object")
    if obj.get("protocol") != PROTOCOL or obj.get("version") != VERSION:
        raise ValueError("queue_protocol_mismatch")
    tasks = obj.get("tasks")
    if not isinstance(tasks, list) or len(tasks) > MAX_TASKS:
        raise ValueError("invalid_task_list")
    return obj


def _resolve_queue_main_sha() -> str | None:
    req = urllib.request.Request(
        QUEUE_REFS_URL,
        headers={
            "User-Agent": "powerpc-control-v1/1",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read(512 * 1024)
        matches = {
            item.decode("ascii")
            for item in re.findall(
                rb"([0-9a-f]{40}) refs/heads/main(?:\x00|\n)",
                raw,
            )
        }
        if len(matches) != 1:
            raise ValueError("queue_main_ref_ambiguous")
        return next(iter(matches))
    except Exception as e:
        _log("queue_ref_error=" + type(e).__name__)
        return None


def _fetch_queue_immutable() -> dict[str, Any] | None:
    sha = _resolve_queue_main_sha()
    if sha is None:
        return None
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        _log("queue_ref_error=InvalidSha")
        return None
    url = QUEUE_IMMUTABLE_URL_TEMPLATE.format(sha=sha)
    url += ("&" if "?" in url else "?") + "t=" + str(time.time_ns())
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "powerpc-control-v1/1",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read(MAX_QUEUE_BYTES + 1)
        return _parse_queue_bytes(raw)
    except Exception as e:
        _log("queue_immutable_error=" + type(e).__name__)
        return None


def _fetch_queue_raw() -> dict[str, Any] | None:
    url = QUEUE_URL + ("&" if "?" in QUEUE_URL else "?") + "t=" + str(time.time_ns())
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "powerpc-control-v1/1",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read(MAX_QUEUE_BYTES + 1)
        return _parse_queue_bytes(raw)
    except Exception as e:
        _log("queue_raw_error=" + type(e).__name__)
        return None


def _fetch_queue_api() -> dict[str, Any] | None:
    req = urllib.request.Request(
        QUEUE_API_URL,
        headers={
            "User-Agent": "powerpc-control-v1/1",
            "Accept": "application/vnd.github+json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read((MAX_QUEUE_BYTES * 2) + 65536)
        wrapper = json.loads(raw.decode("utf-8"))
        if not isinstance(wrapper, dict):
            raise ValueError("queue_api_not_object")
        if wrapper.get("encoding") != "base64" or not isinstance(wrapper.get("content"), str):
            raise ValueError("queue_api_content_missing")
        payload = base64.b64decode(wrapper["content"], validate=False)
        return _parse_queue_bytes(payload)
    except Exception as e:
        _log("queue_api_error=" + type(e).__name__)
        return None


def _fetch_queue() -> dict[str, Any] | None:
    global _LAST_API_FALLBACK_MONO

    immutable_obj = _fetch_queue_immutable()
    if immutable_obj is not None:
        return immutable_obj

    # Compatibility fallback only. Branch-content endpoints may lag and must
    # never outrank an immutable-SHA read when ref resolution succeeds.
    raw_obj = _fetch_queue_raw()
    now = time.monotonic()
    if now - _LAST_API_FALLBACK_MONO >= API_FALLBACK_SECONDS:
        _LAST_API_FALLBACK_MONO = now
        api_obj = _fetch_queue_api()
        if api_obj is not None:
            if raw_obj is not None:
                raw_sha = hashlib.sha256(_canon(raw_obj)).hexdigest()[:16]
                api_sha = hashlib.sha256(_canon(api_obj)).hexdigest()[:16]
                if raw_sha != api_sha:
                    _log("queue_branch_stale raw_sha=" + raw_sha + " api_sha=" + api_sha)
            return api_obj
    return raw_obj

def _aad(task: dict[str, Any]) -> bytes:
    fields = {
        "protocol": task.get("protocol"),
        "version": task.get("version"),
        "task_id": task.get("task_id"),
        "target_runtime_id": task.get("target_runtime_id"),
        "created_at": task.get("created_at"),
        "expires_at": task.get("expires_at"),
        "origin_ephemeral_x25519_spki_b64": task.get("origin_ephemeral_x25519_spki_b64"),
    }
    return _canon(fields)


def _derive(shared: bytes, task_id: str, purpose: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=task_id.encode("utf-8"),
        info=b"powerpc-control-v1/" + purpose,
    ).derive(shared)


def _validate_outer(task: dict[str, Any]) -> tuple[bool, str]:
    if task.get("protocol") != PROTOCOL or task.get("version") != VERSION:
        return False, "protocol_mismatch"
    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not (8 <= len(task_id) <= 128):
        return False, "bad_task_id"
    if not all(c.isalnum() or c in "._-" for c in task_id):
        return False, "bad_task_id"
    if task.get("target_runtime_id") != RUNTIME_ID:
        return False, "wrong_runtime"
    try:
        created = int(task["created_at"])
        expires = int(task["expires_at"])
    except Exception:
        return False, "bad_time"
    now = int(time.time())
    if created > now + MAX_CLOCK_SKEW:
        return False, "created_in_future"
    if expires < now:
        return False, "expired"
    if expires > now + MAX_FUTURE_SECONDS:
        return False, "expiry_too_far"
    for key in ("origin_ephemeral_x25519_spki_b64", "nonce_b64", "ciphertext_b64"):
        if not isinstance(task.get(key), str) or not task[key]:
            return False, "missing_" + key
    return True, "ok"


def _decrypt_task(task: dict[str, Any], xpriv) -> tuple[dict[str, Any], bytes]:
    peer = serialization.load_der_public_key(_b64d(task["origin_ephemeral_x25519_spki_b64"]))
    if not isinstance(peer, x25519.X25519PublicKey):
        raise ValueError("origin_key_not_x25519")
    shared = xpriv.exchange(peer)
    key = _derive(shared, task["task_id"], b"command")
    plain = AESGCM(key).decrypt(
        _b64d(task["nonce_b64"]),
        _b64d(task["ciphertext_b64"]),
        _aad(task),
    )
    obj = json.loads(plain.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("payload_not_object")
    return obj, shared


def _validate_payload(task: dict[str, Any], payload: dict[str, Any]) -> None:
    if payload.get("task_id") != task["task_id"]:
        raise ValueError("task_id_mismatch")
    if payload.get("target_runtime_id") != RUNTIME_ID:
        raise ValueError("payload_wrong_runtime")
    tool = payload.get("tool")
    if tool not in ALLOWED_TOOLS:
        raise TaskReject("tool_not_allowed", "NEEDS_AUTHORITY")
    allowed = payload.get("allowed_capability_profile")
    if not isinstance(allowed, list) or tool not in allowed or any(x not in ALLOWED_TOOLS for x in allowed):
        raise TaskReject("capability_profile_reject", "NEEDS_AUTHORITY")
    ceiling = payload.get("authority_ceiling")
    if ceiling not in ("read_only", "bounded_operator"):
        raise TaskReject("authority_ceiling_reject", "NEEDS_AUTHORITY")
    if ceiling == "read_only" and tool == "terminal_exec":
        raise TaskReject("authority_attenuation_reject", "NEEDS_AUTHORITY")
    # Even encrypted, authenticated bounded_operator envelopes do not prove
    # a live destination claim/run/fence/CAS. The provider's task transport
    # and the owner-scoped mutation authority are separate admission layers.
    if tool == "terminal_exec":
        raise TaskReject("destination_mutation_admission_unverified", "BLOCKED")
    if not isinstance(payload.get("arguments", {}), dict):
        raise ValueError("arguments_not_object")


def _call_local_mcp(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if not HELPER.is_file():
        raise RuntimeError("local_mcp_helper_missing")
    inp = _canon({"tool": tool, "arguments": arguments})
    cp = subprocess.run(
        [str(WEBAPP / ".local" / "node22-glibc217" / "bin" / "node"), str(HELPER)],
        input=inp,
        capture_output=True,
        cwd=str(WEBAPP),
        timeout=45,
        env={
            **os.environ,
            "HOME": str(ACCOUNT),
            "PATH": str(WEBAPP / ".local" / "node22-glibc217" / "bin") + ":" + str(WEBAPP / "miniconda" / "bin") + ":/usr/local/bin:/usr/bin:/bin",
        },
    )
    out = cp.stdout[-MAX_RESULT_PLAINTEXT:]
    err = cp.stderr[-12000:]
    if cp.returncode != 0:
        raise RuntimeError("local_mcp_call_failed:" + err.decode("utf-8", "replace")[:4000])
    obj = json.loads(out.decode("utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError("local_mcp_result_not_object")
    return obj


def _result_envelope(task: dict[str, Any], shared: bytes, spriv, result: dict[str, Any]) -> dict[str, Any]:
    plaintext = _canon(result)
    if len(plaintext) > MAX_RESULT_PLAINTEXT:
        plaintext = _canon({
            "task_id": task["task_id"],
            "completion_state": "FAILED",
            "error": "result_too_large",
        })
    key = _derive(shared, task["task_id"], b"result")
    nonce = os.urandom(12)
    aad = _canon({
        "protocol": PROTOCOL,
        "version": VERSION,
        "task_id": task["task_id"],
        "target_runtime_id": RUNTIME_ID,
        "kind": "result",
    })
    cipher = AESGCM(key).encrypt(nonce, plaintext, aad)
    body = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "task_id": task["task_id"],
        "target_runtime_id": RUNTIME_ID,
        "kind": "result",
        "published_at": int(time.time()),
        "nonce_b64": _b64e(nonce),
        "ciphertext_b64": _b64e(cipher),
    }
    body["signature_b64"] = _b64e(spriv.sign(_canon(body)))
    return body


def _publish_result(task: dict[str, Any], shared: bytes, spriv, result: dict[str, Any]) -> str:
    env = _result_envelope(task, shared, spriv, result)
    path = RESULTS / (task["task_id"] + ".json")
    data = _canon(env) + b"\n"
    _atomic_write(path, data, 0o644)
    for mirror in PUBLIC_MIRRORS:
        leaf = task["task_id"] + ".json"
        _atomic_write(mirror / "results" / leaf, data, 0o644)
        _atomic_write(mirror / "ppc-control-results" / leaf, data, 0o644)
        _atomic_write(mirror / PROTOCOL / "results" / leaf, data, 0o644)
        # Some public frontends pass flat static JSON files while blocking nested
        # static paths. Publish a task-scoped flat alias as an additive egress
        # compatibility route; the signed/encrypted envelope remains unchanged.
        _atomic_write(mirror / ("powerpc-control-result-" + leaf), data, 0o644)
        _atomic_write(mirror / ("ppc-control-result-" + leaf), data, 0o644)
    return str(path)


def _failure_result(task: dict[str, Any], error: str, completion_state: str = "FAILED") -> dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "executor_identity": {
            "runtime_id": RUNTIME_ID,
            "user": os.environ.get("USER", "unknown"),
            "uid": os.getuid(),
            "hostname": socket.gethostname(),
        },
        "runtime_receipt": {"namespace": str(ACCOUNT), "webapp": str(WEBAPP)},
        "actions": [],
        "evidence_refs": [],
        "result": None,
        "unresolved": [error],
        "resource_usage": {},
        "completion_state": completion_state,
    }


def _commit_task_final_state(
    conn: sqlite3.Connection, task_id: str, state: str,
    result_path: str | None = None, *, attempts: int = 3,
) -> bool:
    """Bounded DB finalization. Never rerun an already attempted tool.

    A private signed result may have been published even if the DB commit is
    unavailable. In that case preserve the original 'claimed' record as an
    outcome requiring reconciliation. No retry of the destination effect.
    """
    for attempt in range(attempts):
        try:
            if result_path is None:
                conn.execute("UPDATE tasks SET state=? WHERE task_id=?",
                             (state, task_id))
            else:
                conn.execute(
                    "UPDATE tasks SET state=?,completed_at=?,result_path=? WHERE task_id=?",
                    (state, int(time.time()), result_path, task_id),
                )
            conn.commit()
            return True
        except sqlite3.Error as exc:
            # A failed commit can retain an open SQLite transaction; retrying
            # without rollback can self-deadlock even after external locks end.
            try:
                conn.rollback()
            except sqlite3.Error:
                _log("db_rollback_unresolved=" + task_id)
                return False
            _log("db_finalization_unresolved=" + task_id + ":" + type(exc).__name__)
            if not isinstance(exc, sqlite3.OperationalError) or "locked" not in str(exc).lower():
                return False
            if attempt + 1 < attempts:
                time.sleep(min(0.1 * (attempt + 1), 0.3))
    return False


def _process_task(task: dict[str, Any], xpriv, spriv, conn: sqlite3.Connection) -> None:
    valid, why = _validate_outer(task)
    task_id = task.get("task_id") if isinstance(task.get("task_id"), str) else ""
    if not task_id:
        return
    if not valid and why != "expired":
        return

    envelope_hash = hashlib.sha256(_canon(task)).hexdigest()
    try:
        row = conn.execute("SELECT envelope_sha256,state FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    except sqlite3.Error as exc:
        _log("db_claim_read_unresolved=" + task_id + ":" + type(exc).__name__)
        return
    if row:
        if row[0] == envelope_hash:
            return
        try:
            _payload, shared = _decrypt_task(task, xpriv)
            receipt = _failure_result(task, "task_id_conflict", "FAILED")
            _publish_result(task, shared, spriv, receipt)
        except Exception:
            pass
        _log("task_conflict=" + task_id)
        return

    try:
        payload, shared = _decrypt_task(task, xpriv)
    except Exception as e:
        _log("decrypt_reject=" + task_id + ":" + type(e).__name__)
        return

    now = int(time.time())
    initial_state = "expired" if not valid and why == "expired" else "claimed"
    try:
        conn.execute(
            "INSERT INTO tasks(task_id,envelope_sha256,state,received_at) VALUES(?,?,?,?)",
            (task_id, envelope_hash, initial_state, now),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return
    except sqlite3.Error as exc:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        _log("db_claim_write_unresolved=" + task_id + ":" + type(exc).__name__)
        # A failed durable claim must never advance to local-MCP execution.
        return

    if initial_state == "expired":
        receipt = _failure_result(task, "expired", "EXPIRED")
    else:
        try:
            _validate_payload(task, payload)
            tool = payload["tool"]
            result_obj = _call_local_mcp(tool, payload.get("arguments", {}))
            receipt = {
                "task_id": task_id,
                "executor_identity": {
                    "runtime_id": RUNTIME_ID,
                    "user": os.environ.get("USER", "unknown"),
                    "uid": os.getuid(),
                    "hostname": socket.gethostname(),
                },
                "runtime_receipt": {
                    "namespace": str(ACCOUNT),
                    "webapp": str(WEBAPP),
                    "local_mcp": str(WEBAPP / "bin" / "local-mcp"),
                },
                "actions": [{"capability": tool, "arguments_sha256": hashlib.sha256(_canon(payload.get("arguments", {}))).hexdigest()}],
                "evidence_refs": [],
                "result": result_obj,
                "unresolved": [],
                "resource_usage": {"transport": "github-poll+https-result", "local_mcp_calls": 1},
                "completion_state": "COMPLETED" if not result_obj.get("isError") else "FAILED",
            }
        except TaskReject as e:
            receipt = _failure_result(task, str(e), e.completion_state)
        except Exception as e:
            receipt = _failure_result(task, type(e).__name__ + ":" + str(e)[:1200], "FAILED")

    try:
        result_path = _publish_result(task, shared, spriv, receipt)
    except Exception as exc:
        # Do not let a second SQLite failure in the error handler terminate
        # the entire daemon or invite blind tool re-execution.
        persisted = _commit_task_final_state(conn, task_id, "publish_failed")
        _log("publish_error=" + task_id + ":" + type(exc).__name__
             + (" persisted" if persisted else " db_unresolved"))
        return

    persisted = _commit_task_final_state(
        conn, task_id, receipt["completion_state"].lower(), result_path
    )
    if persisted:
        _log("task=" + task_id + " state=" + receipt["completion_state"])
    else:
        # Published result is durable, but metadata is not. Existing claimed
        # task_id suppresses replay until separately verified reconciliation.
        _log("result_published_db_unresolved=" + task_id)


def _signal(_signum, _frame):
    global STOP
    STOP = True


def main() -> int:
    if os.getuid() != EXPECTED_UID and os.environ.get("PPC_CONTROL_ALLOW_TEST_UID") != "1":
        print(f"REFUSED uid={os.getuid()} expected={EXPECTED_UID}", file=sys.stderr)
        return 2
    if not WEBAPP.is_dir() or not HTDOCS.is_dir():
        print("REFUSED canonical paths unavailable", file=sys.stderr)
        return 2
    signal.signal(signal.SIGTERM, _signal)
    signal.signal(signal.SIGINT, _signal)
    STATE.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    for mirror in PUBLIC_MIRRORS:
        mirror.mkdir(parents=True, exist_ok=True)
        (mirror / "results").mkdir(parents=True, exist_ok=True)
        (mirror / "ppc-control-results").mkdir(parents=True, exist_ok=True)
        (mirror / PROTOCOL / "results").mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    xpriv, spriv = _load_or_create_keys()
    conn = _db()
    _atomic_write(PIDFILE, (str(os.getpid()) + "\n").encode(), 0o600)
    started = int(time.time())
    last_heartbeat = 0
    _log("daemon_start pid=" + str(os.getpid()))
    try:
        while not STOP:
            now = int(time.time())
            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                _publish_identity(xpriv, spriv, started)
                last_heartbeat = now
            q = _fetch_queue()
            if q:
                for task in q.get("tasks", []):
                    if STOP:
                        break
                    if isinstance(task, dict):
                        _process_task(task, xpriv, spriv, conn)
            time.sleep(POLL_SECONDS)
    finally:
        try:
            # PIDFILE is shared across replacement generations.  An older
            # daemon may finish after a newer daemon has already published its
            # PID, so only remove the file when we still own it.
            owner = PIDFILE.read_text(encoding="ascii").strip()
            if owner == str(os.getpid()):
                PIDFILE.unlink()
        except FileNotFoundError:
            pass
        except (OSError, UnicodeError):
            # Cleanup must never turn normal daemon shutdown into a failure.
            pass
        conn.close()
        _log("daemon_stop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
