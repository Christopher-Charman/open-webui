#!/usr/bin/env python3
"""Read-only Ollama evidence collector for the PowerPC OpenWebUI recovery lane."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

BASE = Path("/home/storage/781/4477781/user/webapp")
OLLAMA_URL = "http://127.0.0.1:11434"


def tcp_open(host: str, port: int, timeout: float = 0.75) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def http_json(path: str, timeout: float = 2.5) -> tuple[int | None, Any]:
    try:
        with urllib.request.urlopen(OLLAMA_URL + path, timeout=timeout) as r:
            body = r.read(2_000_000)
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = body.decode("utf-8", "replace")[:2000]
            return r.status, parsed
    except Exception:
        return None, None


def pgrep_ollama() -> list[str]:
    try:
        out = subprocess.check_output(
            ["pgrep", "-af", "ollama"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return [line for line in out.splitlines() if line.strip()]
    except Exception:
        return []


def launcher_candidates() -> list[dict[str, Any]]:
    candidates = [
        BASE / "bin" / "ollama",
        BASE / "ollama",
        BASE / "run-ollama.sh",
        BASE / "start-ollama.sh",
        BASE / "restart-ollama.sh",
        BASE / "bin" / "run-ollama",
    ]
    out = []
    for p in candidates:
        if p.exists():
            out.append({
                "path": str(p),
                "is_file": p.is_file(),
                "executable": os.access(p, os.X_OK),
                "size": p.stat().st_size if p.is_file() else None,
            })
    return out


def log_candidates() -> list[dict[str, Any]]:
    names = [
        "ollama.log",
        "logs/ollama.log",
        "runtime-domains/ollama/ollama.log",
        "runtime-domains/ollama/logs/ollama.log",
    ]
    out = []
    for rel in names:
        p = BASE / rel
        if not p.is_file():
            continue
        try:
            lines = p.read_text(errors="replace").splitlines()[-30:]
        except Exception:
            lines = []
        out.append({"path": str(p), "tail": lines})
    return out


def main() -> int:
    version_status, version_body = http_json("/api/version")
    tags_status, tags_body = http_json("/api/tags")

    models = []
    if isinstance(tags_body, dict):
        for m in tags_body.get("models") or []:
            if isinstance(m, dict):
                name = m.get("name") or m.get("model")
                if name:
                    models.append(str(name))

    processes = pgrep_ollama()
    evidence = {
        "port_open": tcp_open("127.0.0.1", 11434),
        "process_running": bool(processes),
        "processes": processes,
        "version_http": version_status,
        "version": version_body.get("version") if isinstance(version_body, dict) else None,
        "tags_http": tags_status,
        "models": models,
        "ollama_on_path": shutil.which("ollama"),
        "launcher_candidates": launcher_candidates(),
        "log_candidates": log_candidates(),
    }
    print(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
