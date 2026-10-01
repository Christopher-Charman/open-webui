#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path

base=Path("/home/storage/781/4477781/user/webapp")
pkg=base/"envs/openwebui/lib/python3.11/site-packages/open_webui"
static=pkg/"static"
front=pkg/"frontend"
names=[
 "continuity-orb-beam-postmount.js",
 "owui-orb-v1.js",
 "owui-orb-v1.css",
 "continuity-theme-stable-binder.js",
 "continuity-theme-stable-binder.css",
 "continuity-neural-material.js",
 "continuity-neural-material.css",
 "continuity-theme-overlay.css"
]
out={"schema":"openwebui-presentation-source-snapshot-v1","mutation":"NONE","files":{}}
for n in names:
    p=static/n
    if p.is_file():
        t=p.read_text(errors="replace")
        out["files"][n]={"size":len(t.encode()),"content":t}
idx=front/"index.html"
if idx.is_file():
    out["index"]=idx.read_text(errors="replace")
print(json.dumps(out,sort_keys=True,separators=(",",":")))
