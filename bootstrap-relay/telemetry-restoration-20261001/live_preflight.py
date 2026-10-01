#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

base=None
for c in [Path.home(),Path.home()/"webapp",Path.cwd(),Path.cwd()/"webapp"]:
    if (c/"envs/openwebui/lib/python3.11/site-packages/open_webui").is_dir():
        base=c.resolve();break
if base is None: raise SystemExit("BASE_UNRESOLVED")
pkg=base/"envs/openwebui/lib/python3.11/site-packages/open_webui"
static=pkg/"static"; front=pkg/"frontend"; index=front/"index.html"

def inspect(name,include=False):
    p=static/name
    if not p.is_file(): return {"name":name,"present":False}
    text=p.read_text(errors="replace")
    out={"name":name,"present":True,"size":p.stat().st_size,"sha256":sha(p)}
    if include: out["content"]=text
    return out

voice=inspect("pwa-voice-bridge.js")
if voice["present"]:
    t=(static/"pwa-voice-bridge.js").read_text(errors="replace")
    voice["markers"]=[line.strip() for line in t.splitlines() if any(k in line for k in (
        "VERSION","version","warmSelectedVoice","local-voice/warm","speechSynthesis","Cortana","Majel","Kokoro"
    ))][:160]
    voice["forbidden_counts"]={k:t.count(k) for k in ("warmSelectedVoice","/api/v1/audio/local-voice/warm","observer.observe")}
hero=inspect("continuity-shell-hero-presenter.js")
if hero["present"]:
    t=(static/"continuity-shell-hero-presenter.js").read_text(errors="replace")
    hero["version_lines"]=[x.strip() for x in t.splitlines() if "VERSION" in x][:12]
orb=inspect("owui-orb-v1.js")
if orb["present"]:
    t=(static/"owui-orb-v1.js").read_text(errors="replace")
    orb["version_lines"]=[x.strip() for x in t.splitlines() if "ORB_VERSION" in x or "version" in x.lower()][:20]
stable_js=inspect("continuity-theme-stable-binder.js",True)
stable_css=inspect("continuity-theme-stable-binder.css",True)
idx=index.read_text(errors="replace")
out={
 "schema":"openwebui-telemetry-preflight-v1",
 "mutation":"NONE",
 "base":str(base),
 "index":{"sha256":sha(index),"size":index.stat().st_size,"refs":[x.strip() for x in idx.splitlines() if any(k in x.lower() for k in ("continuity-shell","continuity-theme","owui-orb","border-beam","pwa-voice"))]},
 "loader":inspect("loader.js"),
 "custom_css":inspect("custom.css"),
 "voice":voice,
 "hero":hero,
 "orb":orb,
 "stable_binder_js":stable_js,
 "stable_binder_css":stable_css
}
print(json.dumps(out,sort_keys=True,separators=(",",":")))
