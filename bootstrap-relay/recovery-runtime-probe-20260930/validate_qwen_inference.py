#!/usr/bin/env python3
"""Bounded direct inference validator for the selected Local Agent Qwen model."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

OLLAMA_GENERATE = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5-coder:1.5b-instruct-q4_K_M"
SENTINEL = "QWEN_LOCAL_AGENT_OK"


def classify_qwen_response(status: int | None, body: Any) -> dict[str, Any]:
    response = body.get("response") if isinstance(body, dict) else None
    done = body.get("done") if isinstance(body, dict) else None
    ok = bool(status == 200 and isinstance(response, str) and SENTINEL in response)
    return {
        "state": "PASS" if ok else "FAIL",
        "http_status": status,
        "done": done,
        "sentinel_present": bool(isinstance(response, str) and SENTINEL in response),
        "response_excerpt": response[:240] if isinstance(response, str) else None,
    }


def validate_qwen_inference(timeout: float = 20.0) -> dict[str, Any]:
    payload = {
        "model": MODEL,
        "prompt": (
            "This is a deterministic health check. "
            "Reply with exactly this token and nothing else: "
            + SENTINEL
        ),
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 24,
        },
    }
    req = urllib.request.Request(
        OLLAMA_GENERATE,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(2_000_000)
            try:
                body = json.loads(raw)
            except Exception:
                body = {"response": raw.decode("utf-8", "replace")}
            result = classify_qwen_response(r.status, body)
    except Exception as exc:
        result = {
            "state": "FAIL",
            "http_status": None,
            "done": None,
            "sentinel_present": False,
            "response_excerpt": None,
            "error": type(exc).__name__ + ":" + str(exc),
        }

    result["model"] = MODEL
    result["mutation"] = "NONE"
    return result


def main() -> int:
    out = validate_qwen_inference()
    print(json.dumps(out, sort_keys=True, separators=(",", ":")))
    return 0 if out.get("state") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
