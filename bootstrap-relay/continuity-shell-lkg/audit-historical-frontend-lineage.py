#!/usr/bin/env python3
from pathlib import Path
import hashlib, os, re, time

BASE=Path("/home/storage/781/4477781/user/webapp")
PKG=BASE/"envs/openwebui/lib/python3.11/site-packages/open_webui"
PWA=BASE/"runtime-domains/pwa-repair-agent/backups"

MARKERS=[
    "custom-shell-landing","custom-shell-prompt","custom-shell-sidebar",
    "custom-shell-sidebar-rail","custom-shell-footer",
    "custom-shell-model-selector-panel","custom-shell-settings-modal",
    "custom-shell-controls","custom-shell-workspace-models",
    "custom-shell-agent-name","custom-shell-agent-description",
    "hero-network","hero-aura","chat-landing-network","chat-landing-aura",
    "orb-slot","chat-telemetry",
    "COMPUTER CORE","WORLD BETWEEN WORLDS",
    "Continuity Shell · Open WebUI","INPUT"
]
WRITER_HINTS=[
    "classList","className","setAttribute","querySelector","querySelectorAll",
    "MutationObserver","createElement","insertBefore","appendChild","prepend",
    "class=","class:"
]
TEXT_EXT={".js",".html",".css",".svelte",".ts",".mjs",".map"}

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def mtime(p):
    try: return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.stat().st_mtime))
    except: return "?"

roots=[]

# Full historical package frontends are the primary missing search surface.
if PKG.exists():
    for p in PKG.iterdir():
        if p.is_dir() and p.name.startswith("frontend"):
            roots.append(p)

# Also include frontend snapshots under repair backups.
if PWA.exists():
    for p in PWA.iterdir():
        if not p.is_dir(): continue
        f=p/"frontend"
        if f.is_dir():
            roots.append(f)

# Deduplicate.
seen=set(); uniq=[]
for r in roots:
    s=str(r)
    if s not in seen:
        seen.add(s); uniq.append(r)
roots=uniq

print("HISTORICAL_FRONTEND_LINEAGE_AUDIT=BEGIN")
print("mode=READ_ONLY")
print(f"discovered_frontend_roots={len(roots)}")

records=[]
for root in roots:
    marker_files=[]
    marker_set=set()
    writer_score=0
    has_immutable=(root/"_app/immutable").is_dir()
    idx=root/"index.html"
    index_sha=sha(idx) if idx.is_file() else "MISSING"

    # Search likely implementation surfaces only.
    search_dirs=[root]
    for p in root.rglob("*"):
        if not p.is_file(): continue
        if p.suffix.lower() not in TEXT_EXT: continue
        try:
            size=p.stat().st_size
        except:
            continue
        if size>8_000_000: continue
        try:
            t=p.read_text(errors="ignore")
        except:
            continue
        mh=[m for m in MARKERS if m in t]
        if not mh: continue
        wh=[h for h in WRITER_HINTS if h in t]
        marker_set.update(mh)
        writer_score += len(wh)
        marker_files.append((p,mh,wh,t))

    score=len(marker_set)*100 + writer_score*5 + (40 if has_immutable else 0)
    if marker_files:
        records.append((score,root,marker_set,marker_files,has_immutable,index_sha))

records.sort(key=lambda x:(-x[0],str(x[1])))

print("\n=== RANKED FRONTEND COHORTS WITH SHELL MARKERS ===")
for rank,(score,root,mset,mfiles,has_immutable,index_sha) in enumerate(records[:30],1):
    print(f"\nCOHORT={rank}")
    print(f"score={score}")
    print(f"root={root}")
    print(f"mtime={mtime(root)}")
    print(f"has_immutable={'YES' if has_immutable else 'NO'}")
    print(f"index_sha256={index_sha}")
    print("markers="+",".join(sorted(mset)))
    print(f"marker_files={len(mfiles)}")
    for p,mh,wh,t in mfiles[:20]:
        print(f"  file={p}")
        print(f"  sha256={sha(p)}")
        print("  markers="+",".join(mh))
        print("  writer_hints="+",".join(wh))

print("\n=== LIKELY SEMANTIC WRITERS ===")
cands=[]
for score,root,mset,mfiles,has_immutable,index_sha in records:
    for p,mh,wh,t in mfiles:
        if p.suffix.lower() not in {".js",".mjs",".svelte",".ts",".html"}: continue
        if not wh: continue
        cscore=len(mh)*100+len(wh)*10+(30 if has_immutable else 0)
        cands.append((cscore,root,p,mh,wh,t))
cands.sort(key=lambda x:(-x[0],str(x[2])))

print(f"candidate_writer_files={len(cands)}")
for rank,(score,root,p,mh,wh,t) in enumerate(cands[:30],1):
    print(f"\nWRITER={rank}")
    print(f"score={score}")
    print(f"cohort={root}")
    print(f"file={p}")
    print(f"sha256={sha(p)}")
    print("markers="+",".join(mh))
    print("writer_hints="+",".join(wh))
    emitted=0
    for marker in mh:
        for hit in list(re.finditer(re.escape(marker),t))[:2]:
            lo=max(0,hit.start()-900); hi=min(len(t),hit.end()+1500)
            ctx=t[lo:hi].replace("\n"," ")
            print(f"CONTEXT[{marker}]={ctx[:2600]}")
            emitted+=1
            if emitted>=10: break
        if emitted>=10: break

print("\n=== FULL SOURCE CANDIDATES ===")
# Source-level shell implementation may live in historical frontends as Svelte/TS.
src_hits=[]
for root in roots:
    for ext in ("*.svelte","*.ts"):
        for p in root.rglob(ext):
            try:
                if p.stat().st_size>2_000_000: continue
                t=p.read_text(errors="ignore")
            except:
                continue
            mh=[m for m in MARKERS if m in t]
            if mh:
                src_hits.append((root,p,mh,t))
print(f"source_files={len(src_hits)}")
for root,p,mh,t in src_hits[:40]:
    print(f"cohort={root}")
    print(f"file={p}")
    print(f"sha256={sha(p)}")
    print("markers="+",".join(mh))

print("\n=== BOUNDARY ===")
print("loader_restore=FORBIDDEN")
print("voice_bridge_restore=FORBIDDEN")
print("client_runtime_restore=FORBIDDEN")
print("runtime_mutation=NONE")
print("next=USE_HIGHEST_COHERENT_FULL_FRONTEND_WRITER_AS_PRESENTATION_SOURCE")
print("HISTORICAL_FRONTEND_LINEAGE_AUDIT=END")
