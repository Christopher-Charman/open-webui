#!/usr/bin/env python3
import json, os, re, socket, sqlite3, subprocess
from pathlib import Path

ACCOUNT=Path("/home/storage/781/4477781/user")
BASE=ACCOUNT/"webapp"
PKG=BASE/"envs/openwebui/lib/python3.11/site-packages/open_webui"
SSTATIC=PKG/"static"

def emit(k,v): print(f"{k}={v}")
def section(x): print(f"\n=== {x} ===")

section("NETWORK_NAMESPACE")
try: emit("self.netns",os.readlink("/proc/self/ns/net"))
except Exception as e: emit("self.netns","ERR:"+type(e).__name__)

section("OLLAMA_PROCESSES")
pids=[]
for p in Path("/proc").iterdir():
    if not p.name.isdigit(): continue
    try:
        cmd=(p/"cmdline").read_bytes().replace(b"\0",b" ").decode("utf-8","replace").strip()
    except Exception:
        continue
    if "ollama serve" not in cmd: continue
    pids.append(int(p.name))
    emit("ollama.pid",p.name)
    emit("ollama.cmdline",cmd)
    for label,leaf in [("cwd","cwd"),("exe","exe"),("netns","ns/net")]:
        try: emit(f"ollama.{p.name}.{label}",os.readlink(p/leaf))
        except Exception as e: emit(f"ollama.{p.name}.{label}","ERR:"+type(e).__name__)
    try:
        status=(p/"status").read_text(errors="replace")
        for line in status.splitlines():
            if line.startswith(("Name:","Uid:","Gid:")):
                emit(f"ollama.{p.name}.status",line)
    except Exception: pass
    try:
        env={}
        for item in (p/"environ").read_bytes().split(b"\0"):
            if b"=" not in item: continue
            k,v=item.split(b"=",1)
            k=k.decode("utf-8","replace")
            if k in {"HOME","USER","LOGNAME","OLLAMA_HOST","OLLAMA_MODELS","OLLAMA_ORIGINS","OLLAMA_KEEP_ALIVE"}:
                env[k]=v.decode("utf-8","replace")
        for k in sorted(env): emit(f"ollama.{p.name}.env.{k}",env[k])
    except Exception as e:
        emit(f"ollama.{p.name}.env","ERR:"+type(e).__name__)

section("POWERPC_OLLAMA_CANDIDATES")
for p in [
    BASE/"runtime/ollama/bin/ollama",
    BASE/"bin/ollama",
    ACCOUNT/".local/bin/ollama",
    ACCOUNT/".ollama",
    BASE/"runtime/ollama",
]:
    emit("candidate",f"{p}|exists={p.exists()}|exec={os.access(p,os.X_OK) if p.exists() else False}")
seen=0
for root,dirs,files in os.walk(BASE):
    rel=Path(root).relative_to(BASE)
    if len(rel.parts)>=4:
        dirs[:]=[]
    names=list(dirs)+list(files)
    for name in names:
        if "ollama" in name.lower():
            emit("ollama_path",str(Path(root)/name))
            seen+=1
            if seen>=120: break
    if seen>=120: break

section("LAUNCHER_TEXT_MATCHES")
cands=[]
for name in ["passenger_wsgi.py","run-openwebui.sh","start-openwebui.sh",".env"]:
    p=BASE/name
    if p.is_file(): cands.append(p)
for sub in [BASE/"bin",BASE/"runtime-domains",BASE/"scripts"]:
    if sub.is_dir():
        for p in sub.rglob("*"):
            if p.is_file() and ("ollama" in p.name.lower() or p.suffix in {".sh",".py",".env"}):
                if len(p.relative_to(BASE).parts)<=5: cands.append(p)
for p in cands[:120]:
    try:
        lines=p.read_text(errors="replace").splitlines()
    except Exception:
        continue
    hits=[f"{i}:{line[:500]}" for i,line in enumerate(lines,1) if re.search(r"OLLAMA|ollama",line)]
    if hits:
        emit("launcher_file",str(p))
        for h in hits[:60]: emit("launcher_hit",h)

section("MODEL_BINDING_DETAIL")
db=BASE/"openwebui-data/webui.db"
if db.is_file():
    con=sqlite3.connect("file:"+str(db)+"?mode=ro",uri=True)
    cur=con.cursor()
    for mid in ["local-agent-mini-c-agent","continuity-agent"]:
        row=cur.execute("select id,name,base_model_id,is_active,params,meta from model where id=?",(mid,)).fetchone()
        if not row:
            emit("model",mid+"=ABSENT"); continue
        rid,name,base,active,params,meta=row
        emit("model.id",rid); emit("model.name",name); emit("model.base_model_id",base); emit("model.is_active",bool(active))
        for label,val in [("params",params),("meta",meta)]:
            emit(f"model.{rid}.{label}_bytes",len(val or ""))
            try:
                obj=json.loads(val) if isinstance(val,str) and val else val
                if isinstance(obj,dict):
                    emit(f"model.{rid}.{label}_keys",sorted(obj.keys()))
                    safe={k:obj.get(k) for k in ["model","provider","connection","connection_id","functionIds","filterIds","toolIds","tags","capabilities"] if k in obj}
                    if safe: emit(f"model.{rid}.{label}_safe",json.dumps(safe,sort_keys=True,separators=(",",":")))
            except Exception as e:
                emit(f"model.{rid}.{label}_parse","ERR:"+type(e).__name__)
    con.close()

section("VOICE_BRIDGE_CONTEXT")
voice=SSTATIC/"pwa-voice-bridge.js"
if voice.is_file():
    lines=voice.read_text(errors="replace").splitlines()
    emit("voice.lines",len(lines))
    for start,end in [(250,285),(300,330),(610,665),(850,890)]:
        print(f"--- lines {start}-{end} ---")
        for i in range(start,min(end,len(lines))+1):
            print(f"{i}:{lines[i-1]}")

section("END")
print("OLLAMA_VOICE_DIAGNOSTIC=END")
