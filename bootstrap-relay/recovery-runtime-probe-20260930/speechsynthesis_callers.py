#!/usr/bin/env python3
"""Locate live speechSynthesis callers outside the voice bridge."""

import json,re
from pathlib import Path

ROOT=Path("/home/storage/781/4477781/user/webapp/envs/openwebui/lib/python3.11/site-packages/open_webui/static")
PATTERNS=[
    ("speech_speak",re.compile(r"(?:window\.)?speechSynthesis\s*\.\s*speak\s*\(")),
    ("utterance_ctor",re.compile(r"SpeechSynthesisUtterance")),
    ("synth_speak",re.compile(r"\bsynth\s*\.\s*speak\s*\(")),
]
hits=[]
for path in sorted(ROOT.rglob("*.js")):
    if path.name=="pwa-voice-bridge.js":
        continue
    try:
        text=path.read_text(errors="replace")
    except Exception:
        continue
    for kind,pat in PATTERNS:
        for m in pat.finditer(text):
            lo=max(0,m.start()-700); hi=min(len(text),m.end()+900)
            ctx=text[lo:hi].replace("\n","\\n")
            hits.append({
                "file":str(path.relative_to(ROOT)),
                "kind":kind,
                "offset":m.start(),
                "ready_nearby":bool(re.search(r"\bReady\.?\b",ctx,re.I)),
                "context":ctx[:1800],
            })
            if len(hits)>=80:
                break
        if len(hits)>=80:
            break
    if len(hits)>=80:
        break
print(json.dumps({
    "schema":"openwebui-speech-callers-v1",
    "hit_count":len(hits),
    "hits":hits,
    "mutation":"NONE"
},sort_keys=True,separators=(",",":")))
