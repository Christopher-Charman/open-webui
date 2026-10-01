#!/usr/bin/env python3
"""Locate stock/runtime speech callers and PWA cache references outside injected static JS."""

import json,re
from pathlib import Path

ROOTS=[
    Path("/home/storage/781/4477781/user/webapp/envs/openwebui/lib/python3.11/site-packages/open_webui"),
    Path("/home/storage/781/4477781/user/webapp"),
]
PATTERNS=[
    ("speech_speak",re.compile(rb"(?:window\.)?speechSynthesis\s*\.\s*speak\s*\(")),
    ("utterance_ctor",re.compile(rb"SpeechSynthesisUtterance")),
    ("synth_speak",re.compile(rb"\bsynth\s*\.\s*speak\s*\(")),
    ("ready_text",re.compile(rb"Ready\.",re.I)),
]
EXT={".js",".mjs",".html",".map",".json"}
seen=set()
hits=[]
inventory={"files_scanned":0,"bytes_scanned":0}
for root in ROOTS:
    if not root.exists(): continue
    for path in root.rglob("*"):
        try:
            if not path.is_file() or path.suffix.lower() not in EXT: continue
            rp=str(path.resolve())
            if rp in seen: continue
            seen.add(rp)
            if path.name=="pwa-voice-bridge.js": continue
            size=path.stat().st_size
            if size>12_000_000: continue
            data=path.read_bytes()
        except Exception:
            continue
        inventory["files_scanned"]+=1
        inventory["bytes_scanned"]+=len(data)
        matched=[]
        for kind,pat in PATTERNS:
            for m in pat.finditer(data):
                lo=max(0,m.start()-500); hi=min(len(data),m.end()+900)
                ctx=data[lo:hi].decode("utf-8","replace").replace("\n","\\n")
                matched.append({
                    "kind":kind,
                    "offset":m.start(),
                    "context":ctx[:1800]
                })
                if len(matched)>=8: break
            if len(matched)>=8: break
        if matched:
            try: rel=str(path.relative_to(ROOTS[0]))
            except Exception: rel=str(path)
            hits.append({"file":rel,"size":len(data),"matches":matched})
            if len(hits)>=60: break
    if len(hits)>=60: break

# Find service-worker/cache-related files and version strings separately.
cache_files=[]
for path in sorted(ROOTS[0].rglob("*")):
    try:
        if not path.is_file() or path.suffix.lower() not in {".js",".mjs",".html"}: continue
        name=path.name.lower()
        if "service" in name or "worker" in name or "sw"==path.stem.lower():
            data=path.read_text(errors="replace")
            if "cache" in data.lower() or "serviceworker" in data.lower():
                cache_files.append({
                    "file":str(path.relative_to(ROOTS[0])),
                    "size":len(data),
                    "head":data[:1200].replace("\n","\\n"),
                })
                if len(cache_files)>=30: break
    except Exception: pass

print(json.dumps({
    "schema":"openwebui-stock-speech-pwa-locator-v1",
    "inventory":inventory,
    "hit_count":len(hits),
    "hits":hits,
    "cache_files":cache_files,
    "mutation":"NONE"
},sort_keys=True,separators=(",",":")))
