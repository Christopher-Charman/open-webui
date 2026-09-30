#!/usr/bin/env python3
from pathlib import Path
import hashlib, re

BASE = Path("/home/storage/781/4477781/user/webapp")
SITE = BASE / "envs/openwebui/lib/python3.11/site-packages"
BACK = BASE / "runtime-domains/pwa-repair-agent/backups"

KNOWN_WRITER_PATH = SITE / "open_webui/frontend.refinement-regression-20260923T183250Z/_app/immutable/chunks/BkrUj_hp.js"

ORB_JS_SHA = "71fab45c74489a147a3184044574da6d29051684f7848b59c3bb5627d58badc7"
ORB_CSS_SHA = "6d71e7327a98c6c72904de25e0e379a96d78bf450ec8825978db201343a06e63"
CUSTOM_2249_SHA = "258772ad82f3a57516a646c5d42edd6d008f0409e442dc557c32e617915147fc"
CUSTOM_1956_SHA = "475abc34859bc632461e6bd66bef2e2893fdc8e108035ce5a0617461a6469484"
LCARS_2305_SHA = "b5aee24e3a0efe99927bd69ecf25b13b78fa41947863316d19a48edf9e7b4a76"
LCARS_AUDIT_SHA = "f4b49ce2f075fcf7e2c408e8448d86c4a99d82ae7fb4671cde084b126c1caf77"

MARKERS = {
    "custom-shell-landing-prompt": 12,
    "chat-telemetry": 10,
    "custom-shell-motion": 9,
    "orb-slot": 8,
    "hero-network": 7,
    "hero-aura": 7,
    "resolveShellVisualState": 12,
    "engineSize:20": 5,
    "displaySize:27": 5,
    'role="status"': 3,
    'aria-live="polite"': 3,
}
CONTEXT_MARKERS = [
    "custom-shell-landing-prompt",
    "chat-telemetry",
    "orb-slot",
    "resolveShellVisualState",
    "engineSize:20",
    "displaySize:27",
]

def sha(p: Path):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def compact(s, limit=7000):
    return re.sub(r"\s+", " ", s).strip()[:limit]

def ctx(text, needle, before=1800, after=5000):
    i = text.find(needle)
    if i < 0:
        return None
    return text[max(0, i-before):min(len(text), i+after)]

def roots():
    out = []
    if SITE.exists():
        # current package plus every historical open_webui* sibling/snapshot
        for p in sorted(SITE.glob("open_webui*")):
            if p.is_dir():
                out.append(p)
    if BACK.exists():
        out.append(BACK)
    # de-duplicate by resolved-ish string without requiring existence resolution
    seen = set()
    final = []
    for p in out:
        k = str(p)
        if k not in seen:
            seen.add(k)
            final.append(p)
    return final

def candidate_files(names=None, suffix=None):
    seen = set()
    for root in roots():
        try:
            it = root.rglob("*")
        except Exception:
            continue
        for p in it:
            try:
                if not p.is_file():
                    continue
                if names is not None and p.name not in names:
                    continue
                if suffix is not None and p.suffix != suffix:
                    continue
                k = str(p)
                if k in seen:
                    continue
                seen.add(k)
                yield p
            except Exception:
                continue

print("SEMANTIC_WRITER_V2=BEGIN")
print("mode=READ_ONLY")
print("runtime_mutation=NONE")
print("roots=")
for r in roots():
    print(f"  {r}")

print("\n=== KNOWN WRITER PATH ===")
if KNOWN_WRITER_PATH.exists():
    try:
        print(f"known_writer_path=FOUND {KNOWN_WRITER_PATH}")
        print(f"known_writer_sha256={sha(KNOWN_WRITER_PATH)}")
        print(f"known_writer_bytes={KNOWN_WRITER_PATH.stat().st_size}")
    except Exception as e:
        print(f"known_writer_path=ERROR {e}")
else:
    print(f"known_writer_path=ABSENT {KNOWN_WRITER_PATH}")

print("\n=== SEMANTIC WRITER CANDIDATES ===")
candidates = []
for p in candidate_files(suffix=".js"):
    try:
        sz = p.stat().st_size
        if sz < 1000 or sz > 12_000_000:
            continue
        t = p.read_text(errors="ignore")
    except Exception:
        continue
    hits = [m for m in MARKERS if m in t]
    score = sum(MARKERS[m] for m in hits)
    # Require a meaningful shell/telemetry signal, not generic "status".
    if score >= 8 and any(m in hits for m in (
        "custom-shell-landing-prompt","chat-telemetry","orb-slot",
        "resolveShellVisualState","custom-shell-motion"
    )):
        candidates.append((score, len(hits), p, sz, hits, t))

candidates.sort(key=lambda x: (-x[0], -x[1], str(x[2])))
print(f"candidate_count={len(candidates)}")
for i, (score, nh, p, sz, hits, t) in enumerate(candidates[:40], 1):
    try:
        digest = sha(p)
    except Exception:
        digest = "ERROR"
    print(f"CANDIDATE_{i}_SCORE={score}")
    print(f"CANDIDATE_{i}_HITS={','.join(hits)}")
    print(f"CANDIDATE_{i}_PATH={p}")
    print(f"CANDIDATE_{i}_SHA256={digest}")
    print(f"CANDIDATE_{i}_BYTES={sz}")

if candidates:
    score, nh, p, sz, hits, t = candidates[0]
    print("\n=== BEST CANDIDATE CONTEXT ===")
    print(f"BEST_PATH={p}")
    print(f"BEST_SHA256={sha(p)}")
    for needle in CONTEXT_MARKERS:
        c = ctx(t, needle)
        if c:
            print(f"\nCTX[{needle}]={compact(c)}")
else:
    print("SEMANTIC_WRITER=NOT_FOUND")

print("\n=== EXACT ORB V1.4.5 SOURCE ===")
orb_matches = []
for p in candidate_files(names={"owui-orb-v1.js","owui-orb-v1.css"}):
    try:
        d = sha(p)
    except Exception:
        continue
    if d in {ORB_JS_SHA, ORB_CSS_SHA}:
        orb_matches.append((p,d,p.stat().st_size))
for p,d,sz in orb_matches:
    print(f"ORB_MATCH={p} sha256={d} bytes={sz}")
print(f"orb_exact_matches={len(orb_matches)}")

print("\n=== LATE SHELL CSS COHORTS ===")
targets = {
    CUSTOM_2249_SHA:"CUSTOM_2249",
    CUSTOM_1956_SHA:"CUSTOM_1956",
    LCARS_2305_SHA:"LCARS_2305",
    LCARS_AUDIT_SHA:"LCARS_AUDIT",
}
css_matches = []
for p in candidate_files(names={"custom.css","lcars-theme.css"}):
    try:
        d=sha(p)
    except Exception:
        continue
    if d in targets:
        css_matches.append((targets[d],p,d,p.stat().st_size))
for label,p,d,sz in css_matches:
    print(f"{label}={p} sha256={d} bytes={sz}")
print(f"css_exact_matches={len(css_matches)}")

print("\n=== RECOVERY CLASSIFICATION ===")
if candidates:
    print("writer_recovery=SEMANTIC_CANDIDATE_AVAILABLE")
    print("next=EXTRACT_EXACT_DOM_STATE_CONTRACT_FROM_BEST_CANDIDATE")
else:
    print("writer_recovery=COMPILED_WRITER_ABSENT_FROM_RETAINED_HOST_SNAPSHOTS")
    print("next=RECONSTRUCT_POSTMOUNT_ADAPTER_FROM_GIT_SHELL_CSS_PLUS_EXACT_ORB_V1_4_5_PLUS_DEVICE_ACCEPTANCE")
print("stock_loader=DO_NOT_RESTORE")
print("stock_custom_css=DO_NOT_RESTORE")
print("voice_bridge_1_3_4_nowarm=DO_NOT_TOUCH")
print("client_runtime=DO_NOT_RESTORE")
print("SEMANTIC_WRITER_V2=END")
print("RUNTIME_MUTATION=NONE")
