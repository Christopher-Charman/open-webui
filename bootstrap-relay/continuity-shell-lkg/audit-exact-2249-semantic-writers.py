#!/usr/bin/env python3
from pathlib import Path
import hashlib, re

BASE=Path("/home/storage/781/4477781/user/webapp")
SNAP=BASE/"runtime-domains/pwa-repair-agent/backups/pre-stock-bootstrap-isolation-20260929T204428Z/frontend"
LIVE=BASE/"envs/openwebui/lib/python3.11/site-packages/open_webui/frontend"

MARKERS=[
    "custom-shell-landing","custom-shell-prompt","custom-shell-sidebar",
    "custom-shell-sidebar-rail","custom-shell-footer",
    "custom-shell-model-selector-panel","custom-shell-settings-modal",
    "custom-shell-controls","custom-shell-workspace-models",
    "custom-shell-agent-name","custom-shell-agent-description",
    "hero-network","hero-aura","chat-landing-network","chat-landing-aura",
    "orb-slot","chat-telemetry","COMPUTER CORE","WORLD BETWEEN WORLDS"
]
TOKENS=[
    "classList","className","setAttribute","querySelector","querySelectorAll",
    "MutationObserver","createElement","insertBefore","appendChild","prepend",
    "class=","class:"
]

EXCLUDE_NAMES={"loader.js","pwa-voice-bridge.js","pwa-client-runtime.js"}

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def live_matches(rel):
    exact=LIVE/rel
    if exact.is_file():
        return [exact]
    # compiled chunk names may differ; compare basename stem prefix conservatively
    b=rel.name
    out=[]
    for root in (LIVE/"_app/immutable", LIVE/"static"):
        if not root.exists(): continue
        for p in root.rglob(b):
            if p.is_file(): out.append(p)
    return out

rows=[]
roots=[SNAP/"_app/immutable", SNAP/"static"]
for root in roots:
    if not root.exists(): continue
    for p in root.rglob("*.js"):
        if not p.is_file() or p.name in EXCLUDE_NAMES: continue
        try:
            if p.stat().st_size>8_000_000: continue
            t=p.read_text(errors="ignore")
        except Exception:
            continue
        mh=[m for m in MARKERS if m in t]
        if not mh: continue
        th=[x for x in TOKENS if x in t]
        # marker density dominates; DOM writer hints break ties
        score=len(mh)*100+len(th)*7
        rows.append((score,p,t,mh,th))

rows.sort(key=lambda x:(-x[0],str(x[1])))

print("EXACT_2249_SEMANTIC_WRITER_AUDIT=BEGIN")
print("mode=READ_ONLY")
print(f"snapshot={SNAP}")
print(f"candidate_files={len(rows)}")

for rank,(score,p,t,mh,th) in enumerate(rows[:20],1):
    rel=p.relative_to(SNAP)
    print(f"\n=== CANDIDATE {rank} ===")
    print(f"score={score}")
    print(f"relative={rel}")
    print(f"sha256={sha(p)}")
    print(f"bytes={p.stat().st_size}")
    print("markers="+",".join(mh))
    print("writer_tokens="+",".join(th))
    lm=live_matches(rel)
    if lm:
        for lp in lm[:4]:
            print(f"live_match={lp} sha256={sha(lp)} same={'YES' if sha(lp)==sha(p) else 'NO'}")
    else:
        print("live_match=NONE")

    emitted=0
    for m in mh:
        for hit in list(re.finditer(re.escape(m),t))[:2]:
            lo=max(0,hit.start()-650)
            hi=min(len(t),hit.end()+1100)
            ctx=t[lo:hi].replace("\n"," ")
            print(f"CONTEXT[{m}]={ctx[:1900]}")
            emitted+=1
            if emitted>=8: break
        if emitted>=8: break

print("\n=== MARKER OWNERSHIP SUMMARY ===")
for marker in MARKERS:
    owners=[]
    for score,p,t,mh,th in rows:
        if marker in mh:
            owners.append((score,p.relative_to(SNAP),sha(p),th))
    if owners:
        print(f"\nMARKER={marker} owners={len(owners)}")
        for score,rel,h,th in owners[:8]:
            print(f"  score={score} sha256={h} relative={rel} writer_tokens={','.join(th)}")

print("\n=== SAFETY BOUNDARY ===")
print("loader_restore=FORBIDDEN")
print("voice_bridge_restore=FORBIDDEN")
print("client_runtime_restore=FORBIDDEN")
print("runtime_mutation=NONE")
print("next=RECONSTRUCT_BINDER_FROM_EXACT_HISTORICAL_WRITER_ONLY")
print("EXACT_2249_SEMANTIC_WRITER_AUDIT=END")
