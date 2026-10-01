#!/usr/bin/env python3
"""Emit bounded live contexts around voice startup/playback candidates."""

import hashlib
import json
from pathlib import Path

PATH=Path("/home/storage/781/4477781/user/webapp/envs/openwebui/lib/python3.11/site-packages/open_webui/static/pwa-voice-bridge.js")
RANGES=((1,32),(220,292),(420,452),(510,556),(760,798),(868,904))

raw=PATH.read_bytes()
lines=raw.decode("utf-8","replace").splitlines()
chunks=[]
for start,end in RANGES:
    chunks.append({
        "start":start,
        "end":min(end,len(lines)),
        "lines":[{"line":n,"text":lines[n-1][:700]} for n in range(start,min(end,len(lines))+1)]
    })
print(json.dumps({
    "schema":"openwebui-voice-context-v1",
    "path":str(PATH),
    "sha256":hashlib.sha256(raw).hexdigest(),
    "line_count":len(lines),
    "chunks":chunks,
    "mutation":"NONE"
},sort_keys=True,separators=(",",":")))
