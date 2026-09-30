#!/usr/bin/env python3
from pathlib import Path
import hashlib, re

BASE=Path("/home/storage/781/4477781/user/webapp")
SNAP=BASE/"runtime-domains/pwa-repair-agent/backups/pre-stock-bootstrap-isolation-20260929T204428Z"
EXPECTED_LCARS="f4b49ce2f075fcf7e2c408e8448d86c4a99d82ae7fb4671cde084b126c1caf77"

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

print("EXACT_2249_BINDING_AUDIT=BEGIN")
print("mode=READ_ONLY")
print(f"snapshot={SNAP}")

candidates=[
    SNAP/"frontend/static/lcars-theme.css",
    SNAP/"served/static/lcars-theme.css",
]
found=[p for p in candidates if p.is_file() and sha(p)==EXPECTED_LCARS]
if not found:
    print("FAIL=expected_lcars_theme_not_found")
    raise SystemExit(2)
print(f"lcars_theme_exact={found[0]}")
print(f"lcars_theme_sha256={EXPECTED_LCARS}")

print("\n=== SNAPSHOT CORE INVENTORY ===")
names=[
    "index.html","custom.css","loader.js","lcars-theme.css","lcars-runtime.js",
    "continuity-shell-registry.js","continuity-controls.js","continuity-settings.js",
    "pwa-voice-bridge.js","pwa-client-runtime.js","continuity-orb-beam-postmount.js",
    "continuity-postmount-bootstrap.js","continuity-theme-overlay.css"
]
for n in names:
    hits=[]
    for root in (SNAP/"frontend", SNAP/"served"):
        if not root.exists(): continue
        for p in root.rglob(n):
            if p.is_file():
                hits.append(p)
    print(f"\nASSET={n} count={len(hits)}")
    for p in hits[:10]:
        print(f"  sha256={sha(p)} bytes={p.stat().st_size} path={p}")

print("\n=== INDEX LOAD GRAPH ===")
idx=SNAP/"frontend/index.html"
if idx.is_file():
    txt=idx.read_text(errors="ignore")
    print(f"index_sha256={sha(idx)}")
    for line in txt.splitlines():
        if any(k in line for k in (
            "loader.js","custom.css","lcars-theme","lcars-runtime",
            "continuity-shell-registry","continuity-controls","continuity-settings",
            "pwa-voice-bridge","pwa-client-runtime","continuity-orb","postmount"
        )):
            print(line[:1200])
else:
    print("index=MISSING")

print("\n=== SEMANTIC CLASS WRITERS ===")
markers=[
    "custom-shell-landing","custom-shell-prompt","custom-shell-sidebar",
    "custom-shell-footer","hero-network","hero-aura","orb-slot",
    "chat-telemetry","custom-shell-agent-name","custom-shell-agent-description"
]
search_roots=[
    SNAP/"frontend/static",
    SNAP/"frontend/_app/immutable",
]
for marker in markers:
    hits=[]
    for root in search_roots:
        if not root.exists(): continue
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in {".js",".css",".html"}: continue
            try:
                if p.stat().st_size>6_000_000: continue
                t=p.read_text(errors="ignore")
            except Exception:
                continue
            if marker in t:
                hits.append((p,t))
    print(f"\nMARKER={marker} files={len(hits)}")
    for p,t in hits[:15]:
        positions=[m.start() for m in re.finditer(re.escape(marker),t)]
        print(f"  file={p} sha256={sha(p)} occurrences={len(positions)}")
        for pos in positions[:3]:
            lo=max(0,pos-420); hi=min(len(t),pos+700)
            context=t[lo:hi].replace("\n"," ")
            print("    context="+context[:1200])

print("\n=== TELEMETRY TEXT OWNERS ===")
for needle in ("COMPUTER CORE","WORLD BETWEEN WORLDS","INPUT","Continuity Shell · Open WebUI"):
    print(f"\nTEXT={needle}")
    count=0
    for root in search_roots:
        if not root.exists(): continue
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in {".js",".css",".html"}: continue
            try:
                if p.stat().st_size>6_000_000: continue
                t=p.read_text(errors="ignore")
            except Exception:
                continue
            if needle in t:
                count+=1
                pos=t.index(needle)
                print(f"  file={p} sha256={sha(p)}")
                print("    context="+t[max(0,pos-500):min(len(t),pos+900)].replace("\n"," ")[:1500])
    print(f"  files={count}")

print("\n=== VOICE SAFETY INSPECTION ONLY ===")
for root in (SNAP/"frontend/static", SNAP/"served/static"):
    p=root/"pwa-voice-bridge.js"
    if not p.is_file(): continue
    t=p.read_text(errors="ignore")
    print(f"file={p}")
    print(f"sha256={sha(p)}")
    for needle in ("Ready.","warmSelectedVoice","/api/v1/audio/local-voice/warm","observer.observe","speechSynthesis"):
        print(f"  {needle}={'YES' if needle in t else 'NO'}")

print("\n=== LOADER INSPECTION ONLY ===")
for root in (SNAP/"frontend/static", SNAP/"served/static"):
    p=root/"loader.js"
    if not p.is_file(): continue
    t=p.read_text(errors="ignore")
    print(f"file={p} sha256={sha(p)} bytes={p.stat().st_size}")
    for marker in markers:
        if marker in t:
            print(f"  class_writer_candidate={marker}")
    for needle in ("classList.add","MutationObserver","querySelector","custom-shell"):
        print(f"  {needle}={'YES' if needle in t else 'NO'}")

print("\n=== BOUNDARY ===")
print("loader_restore=FORBIDDEN")
print("client_runtime_restore=FORBIDDEN")
print("voice_bridge_restore=FORBIDDEN")
print("next=EXTRACT_ONLY_PRESENTATION_BINDING_AFTER_EVIDENCE")
print("EXACT_2249_BINDING_AUDIT=END")
print("RUNTIME_MUTATION=NONE")
