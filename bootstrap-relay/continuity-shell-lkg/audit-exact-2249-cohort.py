#!/usr/bin/env python3
from pathlib import Path
import hashlib, os, re, time

BASE=Path("/home/storage/781/4477781/user/webapp")
ROOTS=[
    BASE/"envs/openwebui/lib/python3.11/site-packages/open_webui",
    BASE/"runtime-domains/pwa-repair-agent/backups",
]
TARGET_TS="2026-09-28T22:49:13+01:00"

HASHES={
    "pwa-voice-bridge.js":"01159ca3eaa98fc66a938e8461f3f63edc55f2df1fc2292a3af0245d4f07fa3d",
    "lcars-runtime.js":"20f63776f649eef3a2b9e48c51a7a51092e109369c1bd87b5ed616e8087b93c3",
    "lcars-theme.css":"b5aee24e3a0efe99927bd69ecf25b13b78fa41947863316d19a48edf9e7b4a76",
    "continuity-shell-registry.js":"d6b888db17e38d67db609775f8ea21c131e0c86f9dc90b8a964d907502058334",
    "continuity-controls.js":"307f6b03ea0ad82b8b3f97812381d615610a22633d8dd9fd8be1d47bb634deb1",
    "continuity-settings.js":"1f2f7b660032dd49b6457b714fc4af74af270a4a90bcfc1826c55eac29cb7933",
    "custom.css":"258772ad82f3a57516a646c5d42edd6d008f0409e442dc557c32e617915147fc",
}

MARKERS=[
    "COMPUTER CORE",
    "WORLD BETWEEN WORLDS",
    "Continuity Shell",
    "custom-shell-landing",
    "custom-shell-prompt",
    "hero-network",
    "orb-slot",
    "INPUT",
]

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def fmt_mtime(p):
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.stat().st_mtime))
    except Exception:
        return "?"

print("EXACT_2249_COHORT_AUDIT=BEGIN")
print("mode=READ_ONLY")
print("visual_authority_image_time="+TARGET_TS)

all_matches={}
for name,want in HASHES.items():
    hits=[]
    for root in ROOTS:
        if not root.exists(): continue
        try:
            for p in root.rglob(name):
                if not p.is_file(): continue
                try:
                    if sha256(p)==want:
                        hits.append(p)
                except Exception:
                    pass
        except Exception:
            pass
    all_matches[name]=hits
    print(f"\nASSET={name}")
    print(f"sha256={want}")
    print(f"exact_matches={len(hits)}")
    for p in hits[:40]:
        print(f"  mtime={fmt_mtime(p)} path={p}")

# Derive candidate snapshot roots from exact matches.
def snapshot_root(p):
    parts=p.parts
    # Prefer root ending immediately before frontend/static or static.
    s=str(p)
    for token in ("/frontend/static/","/static/"):
        if token in s:
            return Path(s.split(token,1)[0])
    return p.parent

scores={}
members={}
for name,hits in all_matches.items():
    for p in hits:
        r=snapshot_root(p)
        scores[r]=scores.get(r,0)+1
        members.setdefault(r,[]).append((name,p))

print("\n=== COHERENT SNAPSHOT CANDIDATES ===")
for r,score in sorted(scores.items(), key=lambda kv:(-kv[1],str(kv[0])))[:40]:
    print(f"score={score}/{len(HASHES)} root={r}")
    for name,p in sorted(members[r]):
        print(f"  {name} -> {p}")
    for ix in (r/"frontend/index.html", r/"index.html"):
        if ix.is_file():
            print(f"  index={ix} sha256={sha256(ix)} mtime={fmt_mtime(ix)}")
    for app in (r/"frontend/_app/immutable", r/"_app/immutable"):
        if app.is_dir():
            print(f"  immutable={app}")

# Search only textual files near high-scoring candidate roots for visual implementation markers.
top_roots=[r for r,_ in sorted(scores.items(), key=lambda kv:(-kv[1],str(kv[0])))[:12]]
seen=set()
print("\n=== VISUAL MARKER HITS IN TOP COHORTS ===")
for r in top_roots:
    if not r.exists(): continue
    for p in r.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in {".js",".css",".html",".svelte",".ts"}:
            continue
        try:
            if p.stat().st_size>5_000_000: continue
            text=p.read_text(errors="ignore")
        except Exception:
            continue
        found=[m for m in MARKERS if m in text]
        if found:
            key=str(p)
            if key in seen: continue
            seen.add(key)
            print(f"root={r}")
            print(f"  file={p}")
            print(f"  sha256={sha256(p)}")
            print(f"  markers={found}")

print("\n=== SAFETY EXCLUSIONS ===")
print("loader.js=DO_NOT_RESTORE")
print("pwa-client-runtime.js=DO_NOT_RESTORE")
print("continuity-settings.js=INSPECT_ONLY_DO_NOT_DEPLOY")
print("pwa-voice-bridge.js=INSPECT_ONLY_CURRENT_NOWARM_REMAINS_AUTHORITY")
print("EXACT_2249_COHORT_AUDIT=END")
print("RUNTIME_MUTATION=NONE")
