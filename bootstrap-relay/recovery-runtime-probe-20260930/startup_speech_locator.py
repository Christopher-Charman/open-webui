#!/usr/bin/env python3
"""Locate live startup speech/event consumers without mutating runtime state."""

import json
import re
from pathlib import Path

ROOT=Path("/home/storage/781/4477781/user/webapp/envs/openwebui/lib/python3.11/site-packages/open_webui/static")
PATTERNS={
    "ready_literal":re.compile(r"""['"]Ready\.?['"]""",re.I),
    "ready_event":re.compile(r"""(?:emit|dispatchEvent).*ready|ready.*(?:emit|dispatchEvent)""",re.I),
    "client_voice_event":re.compile(r"owui:client-voice|OWUI_VOICE|client-voice",re.I),
    "speak":re.compile(r"\bspeak\s*\(",re.I),
    "speech_synthesis":re.compile(r"speechSynthesis",re.I),
    "audio_play":re.compile(r"\.play\s*\(",re.I),
    "cortana":re.compile(r"\bcortana\b",re.I),
    "system_ready":re.compile(r"system\s+ready",re.I),
}
hits=[]
for path in sorted(ROOT.glob("*.js")):
    lines=path.read_text(errors="replace").splitlines()
    file_matches=[]
    for idx,line in enumerate(lines):
        kinds=[k for k,p in PATTERNS.items() if p.search(line)]
        if kinds:
            file_matches.append((idx,kinds))
    if not file_matches:
        continue
    relevant=set()
    for idx,kinds in file_matches:
        if {"ready_literal","ready_event","client_voice_event","system_ready"} & set(kinds):
            for n in range(max(0,idx-4),min(len(lines),idx+5)):
                relevant.add(n)
    if not relevant:
        continue
    for n in sorted(relevant):
        kinds=[k for k,p in PATTERNS.items() if p.search(lines[n])]
        hits.append({
            "file":path.name,
            "line":n+1,
            "kinds":kinds,
            "text":lines[n][:800],
        })
        if len(hits)>=220:
            break
    if len(hits)>=220:
        break
print(json.dumps({
    "schema":"openwebui-startup-speech-locator-v1",
    "root":str(ROOT),
    "hits":hits,
    "hit_count":len(hits),
    "mutation":"NONE"
},sort_keys=True,separators=(",",":")))
