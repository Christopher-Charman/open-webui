#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND="$PKG/frontend"
FSTATIC="$FRONTEND/static"
SSTATIC="$PKG/static"
INDEX="$FRONTEND/index.html"
PY="$BASE/envs/openwebui/bin/python"
PIDFILE="$BASE/openwebui-runtime.pid"

say(){ printf '%s\n' "$*"; }
section(){ printf '\n=== %s ===\n' "$1"; }
sha(){ if [ -f "$1" ]; then sha256sum "$1" | awk '{print $1}'; else printf 'ABSENT'; fi; }
bytes(){ if [ -f "$1" ]; then wc -c < "$1" | tr -d ' '; else printf 'ABSENT'; fi; }

section "IDENTITY"
say "probe=OPENWEBUI_RECOVERY_READONLY_V2"
say "mutation=NONE"
say "user=$(id -un)"
say "uid=$(id -u)"
say "pwd=$(pwd -P)"
say "base_exists=$([ -d "$BASE" ] && echo YES || echo NO)"
say "pkg_exists=$([ -d "$PKG" ] && echo YES || echo NO)"

section "OPENWEBUI_PROCESS"
pid=""
if [ -f "$PIDFILE" ]; then pid="$(tr -dc '0-9' < "$PIDFILE" || true)"; fi
if [ -n "$pid" ] && [ -r "/proc/$pid/cmdline" ]; then
  say "pid=$pid"
  say "cmdline=$(tr '\0' ' ' < "/proc/$pid/cmdline" | sed 's/[[:space:]]\+/ /g')"
  if [ -r "/proc/$pid/environ" ]; then
    "$PY" - "$pid" <<'PY'
import sys
pid=sys.argv[1]
allow={"ENABLE_OLLAMA_API","OLLAMA_API_BASE_URL","OLLAMA_BASE_URL","OLLAMA_BASE_URLS","DATA_DIR","WEBUI_URL","ENV"}
raw=open("/proc/%s/environ"%pid,"rb").read().split(b"\0")
vals={}
for item in raw:
    if b"=" not in item: continue
    k,v=item.split(b"=",1); k=k.decode("utf-8","replace")
    if k in allow: vals[k]=v.decode("utf-8","replace")
for k in sorted(vals): print("env.%s=%s"%(k,vals[k]))
PY
  fi
else
  say "pid=UNRESOLVED"
fi

section "LOCAL_SERVICE_MATRIX"
"$PY" - <<'PY'
import concurrent.futures, http.client, json, socket

ports=[18080,18082,18083,11434,19900,9900]
def tcp(p):
    s=socket.socket(); s.settimeout(.8)
    try: return p, ("OPEN" if s.connect_ex(("127.0.0.1",p))==0 else "CLOSED")
    finally: s.close()
with concurrent.futures.ThreadPoolExecutor(max_workers=len(ports)) as ex:
    for p,state in sorted(ex.map(tcp,ports)):
        print("port.%s=%s"%(p,state))

targets=[
 ("openwebui.health",18080,"/health"),
 ("tts18082.health",18082,"/health"),
 ("tts18082.models",18082,"/v1/models"),
 ("pocket18083.health",18083,"/health"),
 ("ollama.version",11434,"/api/version"),
 ("ollama.tags",11434,"/api/tags"),
 ("ollama.ps",11434,"/api/ps"),
]
def get(item):
    name,p,path=item
    c=http.client.HTTPConnection("127.0.0.1",p,timeout=1.5)
    try:
        c.request("GET",path)
        r=c.getresponse(); body=r.read(1024*1024)
        return name,r.status,body
    except Exception as e:
        return name,"ERR:"+type(e).__name__,b""
    finally:
        try:c.close()
        except Exception:pass

results={}
with concurrent.futures.ThreadPoolExecutor(max_workers=len(targets)) as ex:
    for name,status,body in ex.map(get,targets):
        results[name]=(status,body)
        print("%s.http=%s"%(name,status))

for key,label in [("ollama.version","ollama_version"),("ollama.tags","ollama_models"),("ollama.ps","ollama_loaded")]:
    status,body=results.get(key,("ERR",b""))
    if status!=200:
        print(label+"_count=UNAVAILABLE" if label!="ollama_version" else label+"=UNAVAILABLE")
        continue
    try:d=json.loads(body.decode("utf-8","replace"))
    except Exception:
        print(label+"_count=INVALID_JSON" if label!="ollama_version" else label+"=INVALID_JSON"); continue
    if label=="ollama_version":
        print("ollama_version="+str(d.get("version","UNKNOWN")))
    else:
        ms=d.get("models") or []
        print(label+"_count="+str(len(ms)))
        singular="ollama_model" if label=="ollama_models" else "ollama_loaded"
        for m in ms:
            print(singular+"="+str(m.get("name") or m.get("model") or ""))
PY
pgrep -af 'ollama serve|/ollama' 2>/dev/null | sed 's/^/ollama_process=/' || true

section "OPENWEBUI_CONFIG_AND_MODEL_BINDING"
DB=""
for c in "$BASE/openwebui-data/webui.db" "$BASE/data/webui.db"; do
  if [ -f "$c" ]; then DB="$c"; break; fi
done
if [ -z "$DB" ]; then DB="$(find "$BASE" -maxdepth 4 -type f -name webui.db -print -quit 2>/dev/null || true)"; fi
if [ -n "$DB" ]; then say "db=$DB"; else say "db=UNRESOLVED"; fi
if [ -n "$DB" ] && [ -x "$PY" ]; then
"$PY" - "$DB" <<'PY'
import json,sqlite3,sys
from collections import Counter
path=sys.argv[1]
con=sqlite3.connect("file:"+path+"?mode=ro",uri=True); cur=con.cursor()
def dec(v):
    if isinstance(v,(bytes,bytearray)): v=v.decode("utf-8","replace")
    try:return json.loads(v) if isinstance(v,str) else v
    except Exception:return v
def safe_api(v):
    v=dec(v)
    if not isinstance(v,dict): return v
    out={}
    for k,e in v.items():
        if not isinstance(e,dict): out[str(k)]="NON_OBJECT"; continue
        out[str(k)]={x:e.get(x) for x in ("enable","connection_type","prefix_id","model_ids","tags") if x in e}
        out[str(k)]["has_key"]=bool(e.get("key")); out[str(k)]["has_headers"]=bool(e.get("headers"))
    return out
keys=["ollama.enable","ollama.base_urls","ollama.api_configs","ui.default_models","ui.default_pinned_models","audio.tts.engine","audio.tts.voice","audio.tts.model"]
try:
    rows=dict(cur.execute("select key,value from config where key in (%s)"%(",".join("?"*len(keys))),keys).fetchall())
    for k in keys:
        if k not in rows: print("config."+k+"=ABSENT"); continue
        v=dec(rows[k]); v=safe_api(v) if k=="ollama.api_configs" else v
        print("config."+k+"="+json.dumps(v,sort_keys=True,separators=(",",":")))
except Exception as e:
    print("config_query=FAIL:"+type(e).__name__+":"+str(e)[:240])

try:
    cols=[r[1] for r in cur.execute("pragma table_info(model)").fetchall()]
    print("model_table_columns="+",".join(cols))
    if {"id","name","base_model_id"}.issubset(cols):
        q="select id,name,base_model_id,is_active from model order by lower(name),id" if "is_active" in cols else "select id,name,base_model_id,1 from model order by lower(name),id"
        data=cur.execute(q).fetchall()
        print("workspace_model_count="+str(len(data)))
        counts=Counter((r[1] or "").strip().lower() for r in data if (r[1] or "").strip())
        for name,count in sorted(counts.items()):
            if count>1: print("duplicate_model_name=%s|count=%s"%(name,count))
        needles=("local agent","mini c-agent","c-agent","starfleet","deepseek","qwen")
        for mid,name,base,active in data:
            blob=" ".join(str(x or "").lower() for x in (mid,name,base))
            if any(n in blob for n in needles):
                print("target_model="+json.dumps({"id":mid,"name":name,"base_model_id":base,"is_active":bool(active)},sort_keys=True,separators=(",",":")))
except Exception as e:
    print("model_query=FAIL:"+type(e).__name__+":"+str(e)[:240])
con.close()
PY
fi

section "FRONTEND_DEPLOYMENT_IDENTITY"
say "index_sha256=$(sha "$INDEX")"
say "loader_bytes=$(bytes "$FSTATIC/loader.js")"
say "custom_css_bytes=$(bytes "$FSTATIC/custom.css")"
if [ -f "$INDEX" ]; then
  for marker in \
    'owui-postmount-ui-voice-v20260929.1' \
    'owui-postmount-orb-beam-v20260930.1' \
    'continuity-shell-semantic-binder-v20260930.2' \
    'continuity-shell-landing-hero-presenter-v20260930.4' \
    'continuity-neural-material.css?v=20260930.2'
  do
    say "index_marker[$marker]=$(grep -Fc "$marker" "$INDEX" || true)"
  done
fi
for n in \
  pwa-voice-bridge.js pwa-client-runtime.js continuity-postmount-bootstrap.js \
  owui-orb-v1.js owui-orb-v1.css continuity-orb-beam-postmount.js \
  continuity-neural-material.js continuity-neural-material.css \
  continuity-shell-semantic-binder.js continuity-shell-semantic-binder.css \
  continuity-shell-hero-presenter.js continuity-shell-hero-presenter.css
do
  say "asset.$n.bytes=$(bytes "$SSTATIC/$n")"
  say "asset.$n.sha256=$(sha "$SSTATIC/$n")"
done

section "VOICE_STARTUP_STATIC_SCAN"
for f in \
  "$SSTATIC/pwa-voice-bridge.js" \
  "$SSTATIC/pwa-client-runtime.js" \
  "$SSTATIC/continuity-postmount-bootstrap.js" \
  "$SSTATIC/continuity-controls.js"
do
  [ -f "$f" ] || continue
  say "scan_file=$f"
  grep -nE 'warmSelectedVoice|/api/v1/audio/local-voice/warm|speechSynthesis|new[[:space:]]+Audio|\.play\(|cortana|Cortana|ready|Ready' "$f" 2>/dev/null \
    | head -60 | sed 's/^/scan_hit=/' || true
done

section "CLASSIFICATION_HINTS"
say "rule=NO_REPAIR_PERFORMED"
say "rule=OLLAMA_LISTENER_THEN_CONFIG_THEN_INVENTORY_THEN_MODEL_BINDING"
say "rule=CACHE_WARMING_NE_AUDIO_PLAYBACK"
say "rule=ACCEPTED_STACK_RESTORE_REMAINS_STAGED_UNTIL_THIS_PROBE_IS_REVIEWED"
say "OPENWEBUI_RECOVERY_READONLY_V2=END"
