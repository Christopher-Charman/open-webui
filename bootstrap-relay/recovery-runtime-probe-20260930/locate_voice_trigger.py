#!/usr/bin/env python3
"""Deterministically localize candidate startup-audio triggers in live OpenWebUI assets."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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


def locate_voice_triggers(
    files: tuple[str, ...] = FILES,
    root: Path = SSTATIC,
    context_radius: int = 2,
) -> dict[str, Any]:
    hits = []
    file_flags = {}

    for name in files:
        path = root / name
        if not path.is_file():
            continue
        lines = path.read_text(errors="replace").splitlines()
        flags = {key: False for key in PATTERNS}

        for idx, line in enumerate(lines):
            matched = [key for key, pattern in PATTERNS.items() if pattern.search(line)]
            if not matched:
                continue
            for key in matched:
                flags[key] = True
            lo = max(0, idx - context_radius)
            hi = min(len(lines), idx + context_radius + 1)
            hits.append({
                "file": name,
                "line": idx + 1,
                "kinds": matched,
                "context": [
                    {"line": n + 1, "text": lines[n][:500]}
                    for n in range(lo, hi)
                ],
            })

        file_flags[name] = flags

    candidate_files = []
    for name, flags in file_flags.items():
        playback = flags["audio_play"] or flags["new_audio"] or flags["speech_synthesis"]
        if flags["ready"] and flags["cortana"] and playback:
            candidate_files.append(name)

    return {
        "state": "CANDIDATE_FOUND" if candidate_files else "NO_SINGLE_FILE_CANDIDATE",
        "candidate_files": candidate_files,
        "file_flags": file_flags,
        "hits": hits[:120],
        "warm_path_present": any(
            f["warm_helper"] or f["warm_endpoint"]
            for f in file_flags.values()
        ),
        "mutation": "NONE",
    }


def main() -> int:
    out = locate_voice_triggers()
    print(json.dumps(out, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
