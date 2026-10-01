#!/usr/bin/env python3
"""Bounded OpenWebUI recovery frontier validator: Qwen inference + voice-trigger localization."""

import json
import re
import urllib.request
from pathlib import Path

MODEL = "qwen2.5-coder:1.5b-instruct-q4_K_M"
SENTINEL = "QWEN_LOCAL_AGENT_OK"
OLLAMA_GENERATE = "http://127.0.0.1:11434/api/generate"
BASE = Path("/home/storage/781/4477781/user/webapp")
SSTATIC = BASE / "envs/openwebui/lib/python3.11/site-packages/open_webui/static"
FILES = (
    "pwa-voice-bridge.js",
    "pwa-client-runtime.js",
    "continuity-postmount-bootstrap.js",
    "continuity-controls.js",
)
PATTERNS = {
    "ready": re.compile(r"\bready\b", re.I),
    "cortana": re.compile(r"\bcortana\b", re.I),
    "audio_play": re.compile(r"\.play\s*\("),
    "new_audio": re.compile(r"\bnew\s+Audio\s*\("),
    "speech_synthesis": re.compile(r"\bspeechSynthesis\b"),
    "warm_helper": re.compile(r"\bwarmSelectedVoice\b"),
    "warm_endpoint": re.compile(r"/api/v1/audio/local-voice/warm"),
}

def qwen():
    payload = {
        "model": MODEL,
        "prompt": "This is a deterministic health check. Reply with exactly this token and nothing else: " + SENTINEL,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 24},
    }
    req = urllib.request.Request(
        OLLAMA_GENERATE,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read(2_000_000))
            response = body.get("response")
            ok = r.status == 200 and isinstance(response, str) and SENTINEL in response
            return {
                "state": "PASS" if ok else "FAIL",
                "http_status": r.status,
                "done": body.get("done"),
                "sentinel_present": bool(isinstance(response, str) and SENTINEL in response),
                "response_excerpt": response[:240] if isinstance(response, str) else None,
                "model": MODEL,
                "mutation": "NONE",
            }
    except Exception as exc:
        return {
            "state": "FAIL",
            "http_status": None,
            "done": None,
            "sentinel_present": False,
            "response_excerpt": None,
            "model": MODEL,
            "error": type(exc).__name__ + ":" + str(exc),
            "mutation": "NONE",
        }

def voice():
    flags = {}
    line_index = {}
    for name in FILES:
        path = SSTATIC / name
        if not path.is_file():
            continue
        f = {key: False for key in PATTERNS}
        lines = path.read_text(errors="replace").splitlines()
        for idx, line in enumerate(lines, start=1):
            for key, pattern in PATTERNS.items():
                if pattern.search(line):
                    f[key] = True
                    line_index.setdefault(name, {}).setdefault(key, []).append(idx)
        flags[name] = f
    candidates = []
    for name, f in flags.items():
        playback = f["audio_play"] or f["new_audio"] or f["speech_synthesis"]
        if f["ready"] and f["cortana"] and playback:
            candidates.append(name)
    return {
        "state": "CANDIDATE_FOUND" if candidates else "NO_SINGLE_FILE_CANDIDATE",
        "candidate_files": candidates,
        "warm_path_present": any(f["warm_helper"] or f["warm_endpoint"] for f in flags.values()),
        "file_flags": flags,
        "line_index": line_index,
        "mutation": "NONE",
    }

print(json.dumps({
    "schema": "openwebui-frontier-validation-v1",
    "qwen": qwen(),
    "voice": voice(),
    "mutation": "NONE",
}, sort_keys=True, separators=(",", ":")))
