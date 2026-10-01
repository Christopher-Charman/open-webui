#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,time
from pathlib import Path

BASE=Path("/home/storage/781/4477781/user/webapp")
PKG=BASE/"envs/openwebui/lib/python3.11/site-packages/open_webui"
ROOTS=[
    BASE/"runtime-domains/pwa-repair-agent/backups",
    BASE/"checkpoints",
    PKG,
    BASE,
]
WANTED={"index.html","loader.js","custom.css","pwa-voice-bridge.js","lcars-theme.css","lcars-runtime.js","owui-orb-v1.js","owui-orb-v1.css","pwa-client-runtime.js","continuity-settings.js","continuity-shell-registry.js"}
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()
out={"schema":"openwebui-lkg1956-backup-probe-v1","mutation":"NONE","candidates":[]}
seen=set()
for root in ROOTS:
    if not root.exists(): continue
    for p in root.rglob("*"):
        try:
            if not p.is_file() or p.name not in WANTED: continue
            rp=str(p.resolve())
            if rp in seen: continue
            seen.add(rp)
            st=p.stat()
            if st.st_mtime < 1790467200 or st.st_mtime > 1790985600: # 2026-09-27..2026-10-03
                continue
            out["candidates"].append({
                "path":str(p),
                "mtime":int(st.st_mtime),
                "size":st.st_size,
                "sha256":sha(p),
            })
        except Exception:
            pass
out["candidates"].sort(key=lambda x:(x["mtime"],x["path"]))
print(json.dumps(out,sort_keys=True,separators=(",",":")))
