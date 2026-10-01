#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
p=Path("/home/storage/781/4477781/user/webapp/envs/openwebui/lib/python3.11/site-packages/open_webui/static/pwa-voice-bridge.js")
raw=p.read_bytes()
lines=raw.decode("utf-8","replace").splitlines()
start,end=798,min(870,len(lines))
print(json.dumps({
 "schema":"openwebui-voice-route-context-v1",
 "sha256":hashlib.sha256(raw).hexdigest(),
 "version_line":lines[3] if len(lines)>3 else None,
 "lines":[{"line":n,"text":lines[n-1][:1000]} for n in range(start,end+1)],
 "mutation":"NONE"
},sort_keys=True,separators=(",",":")))
