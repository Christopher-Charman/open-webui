#!/usr/bin/env python3
"""Read-only frontend and voice evidence collector for OpenWebUI recovery."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path("/home/storage/781/4477781/user/webapp")
PKG = BASE / "envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND = PKG / "frontend"
FSTATIC = FRONTEND / "static"
SSTATIC = PKG / "static"
INDEX = FRONTEND / "index.html"

MARKERS = (
    "owui-postmount-ui-voice-v20260929.1",
    "owui-postmount-orb-beam-v20260930.1",
    "continuity-shell-semantic-binder-v20260930.2",
    "continuity-shell-landing-hero-presenter-v20260930.4",
    "continuity-neural-material.css?v=20260930.2",
)

VOICE_FILES = (
    "pwa-voice-bridge.js",
    "pwa-client-runtime.js",
    "continuity-postmount-bootstrap.js",
    "continuity-controls.js",
)

ASSET_FILES = (
    "pwa-voice-bridge.js",
    "pwa-client-runtime.js",
    "continuity-postmount-bootstrap.js",
    "owui-orb-v1.js",
    "owui-orb-v1.css",
    "continuity-orb-beam-postmount.js",
    "continuity-neural-material.js",
    "continuity-neural-material.css",
    "continuity-shell-semantic-binder.js",
    "continuity-shell-semantic-binder.css",
    "continuity-shell-hero-presenter.js",
    "continuity-shell-hero-presenter.css",
)


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_size(path: Path) -> int | None:
    return path.stat().st_size if path.is_file() else None


def read_text(path: Path, max_chars: int = 250_000) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(errors="replace")
    return text[:max_chars]


def collect_frontend_voice_evidence() -> dict[str, Any]:
    index_text = read_text(INDEX, 1_000_000)
    markers = {marker: index_text.count(marker) for marker in MARKERS}

    assets = {}
    for name in ASSET_FILES:
        p = SSTATIC / name
        assets[name] = {
            "bytes": file_size(p),
            "sha256": sha256(p),
        }

    voice_sources = []
    voice_source_names = []
    for name in VOICE_FILES:
        p = SSTATIC / name
        if not p.is_file():
            continue
        voice_source_names.append(name)
        voice_sources.append(read_text(p))

    frontend = {
        "index_sha256": sha256(INDEX),
        "loader_bytes": file_size(FSTATIC / "loader.js"),
        "loader_sha256": sha256(FSTATIC / "loader.js"),
        "custom_css_bytes": file_size(FSTATIC / "custom.css"),
        "custom_css_sha256": sha256(FSTATIC / "custom.css"),
        "markers": markers,
        "assets": assets,
    }

    return {
        "frontend": frontend,
        "voice_sources": voice_sources,
        "voice_source_names": voice_source_names,
    }


def main() -> int:
    result = collect_frontend_voice_evidence()
    # CLI output intentionally omits raw source bodies; classifiers consume those in-process.
    output = {
        "frontend": result["frontend"],
        "voice_source_names": result["voice_source_names"],
    }
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
