#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os
from pathlib import Path

def sha256(p: Path) -> str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

base=None
for c in [Path.home(),Path.home()/"webapp",Path.cwd(),Path.cwd()/"webapp"]:
    if (c/"envs/openwebui/lib/python3.11/site-packages/open_webui").is_dir():
        base=c.resolve();break
if base is None:
    raise SystemExit("BASE_UNRESOLVED")
pkg=base/"envs/openwebui/lib/python3.11/site-packages/open_webui"
front=pkg/"frontend"
roots=[pkg/"static",front/"static"]
index=front/"index.html"

patterns=("continuity","owui-orb","border-beam","pwa-voice","theme","lcars","wbw","world-between")
assets=[]
seen=set()
for root in roots:
    if not root.is_dir(): continue
    for p in sorted(root.iterdir()):
        if not p.is_file(): continue
        name=p.name.lower()
        if any(k in name for k in patterns) or p.name in {"loader.js","custom.css"}:
            key=str(p.resolve())
            if key in seen: continue
            seen.add(key)
            assets.append({
                "path":str(p),
                "size":p.stat().st_size,
                "sha256":sha256(p)
            })

idx=index.read_text(errors="replace") if index.is_file() else ""
index_refs=[
    line.strip() for line in idx.splitlines()
    if any(k in line.lower() for k in ("continuity-shell","owui-orb","border-beam","pwa-voice"))
]

out={
    "schema":"openwebui-telemetry-census-v1",
    "mutation":"NONE",
    "base":str(base),
    "index":{"path":str(index),"size":index.stat().st_size if index.exists() else None,"sha256":sha256(index) if index.exists() else None},
    "index_refs":index_refs,
    "assets":assets,
    "hero_presenter_present":any("continuity-shell-hero-presenter" in a["path"] for a in assets),
    "orb_present":any("owui-orb" in a["path"] for a in assets),
    "voice_bridge_present":any(a["path"].endswith("pwa-voice-bridge.js") for a in assets),
}
print(json.dumps(out,sort_keys=True,separators=(",",":")))
