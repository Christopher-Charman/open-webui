#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"

echo "NEURAL_LINEAGE_FINGERPRINT=BEGIN"
echo "mode=READ_ONLY"

mapfile -t SNAPS < <(
  find "$PKG" -maxdepth 1 -type d \
    \( -name 'frontend.pre-neural-safe-20260923T175535Z' \
       -o -name 'frontend.pre-connecting-20260923T185145Z' \
       -o -name 'frontend.pre-unified-20260923T202118Z' \
       -o -name 'frontend.pre-hierarchy-20260923T224239Z' \
       -o -name 'frontend.pre-refinement-20260923T150754Z' \
       -o -name 'frontend.pre-refinement-20260923T145921Z' \) \
    -print 2>/dev/null | sort
)

echo "snapshot_count=\${#SNAPS[@]}"

for snap in "\${SNAPS[@]}"; do
  echo
  echo "===== SNAPSHOT $(basename "$snap") ====="

  for rel in index.html static/custom.css static/loader.js static/owui-orb-v1.js static/owui-orb-v1.css; do
    p="$snap/$rel"
    if [ -f "$p" ]; then
      printf 'FILE %s bytes=%s sha256=%s\n' \
        "$rel" "$(wc -c < "$p" | tr -d ' ')" "$(sha256sum "$p" | awk '{print $1}')"
    else
      printf 'FILE %s MISSING\n' "$rel"
    fi
  done

  echo "--- SIGNATURE COUNTS ---"
  python3 - "$snap" <<'PY'
from pathlib import Path
import re, sys

root = Path(sys.argv[1])
patterns = {
    "SYSTEM_READY": r"SYSTEM READY",
    "READY_WORD": r"\bREADY\b|\bReady\b",
    "CONTINUITY_SHELL": r"Continuity Shell",
    "CONTINUITY_AGENT": r"Continuity Agent",
    "NEURAL": r"neural",
    "SPHERE": r"sphere",
    "BORDER_BEAM": r"border[- _]?beam|Border Beam|borderBeam",
    "THINKING_ORB": r"thinking[- _]?orb|owui-thinking-orb-v1",
    "MESSAGE_INPUT": r"message-input-container",
    "LCARS": r"\bLCARS\b",
    "GOO": r"gooey|goo\b",
    "METAL": r"metal",
    "READY_STATE": r"shellState|readyState|state.*ready",
}

files = []
for rel in ("index.html","static/custom.css","static/loader.js","static/owui-orb-v1.js","static/owui-orb-v1.css"):
    p = root / rel
    if p.is_file():
        files.append(p)

app = root / "_app"
if app.is_dir():
    for p in app.rglob("*"):
        if p.is_file() and p.suffix in {".js",".css"}:
            files.append(p)

totals={k:0 for k in patterns}
hits={k:[] for k in patterns}

for p in files:
    try:
        s=p.read_text(errors="ignore")
    except Exception:
        continue
    for k,pat in patterns.items():
        n=len(re.findall(pat,s,flags=re.I))
        if n:
            totals[k]+=n
            if len(hits[k])<8:
                hits[k].append((str(p.relative_to(root)),n))

for k in patterns:
    print(f"SIG {k} count={totals[k]}")
    for rel,n in hits[k]:
        print(f"  {rel} x{n}")
PY

  echo "--- VISUAL TOKEN EXCERPTS ---"
  python3 - "$snap" <<'PY'
from pathlib import Path
import sys

root=Path(sys.argv[1])
terms=[
    "SYSTEM READY",
    "Continuity Shell",
    "Continuity Agent",
    "neural",
    "sphere",
    "border-beam",
    "Border Beam",
    "owui-thinking-orb-v1",
]
seen=0
for p in [root/"index.html", root/"static/custom.css", root/"static/loader.js", root/"static/owui-orb-v1.js", root/"static/owui-orb-v1.css"]:
    if not p.is_file(): continue
    try: s=p.read_text(errors="ignore")
    except Exception: continue
    for term in terms:
        pos=s.lower().find(term.lower())
        if pos>=0:
            lo=max(0,pos-220); hi=min(len(s),pos+520)
            print(f"EXCERPT {p.relative_to(root)} term={term}")
            print(s[lo:hi].replace("\n"," ")[:900])
            seen+=1
            if seen>=24: raise SystemExit
PY

done

echo
echo "=== PAIRWISE STATIC DELTAS ==="
python3 - "$PKG" <<'PY'
from pathlib import Path
import hashlib, sys

pkg=Path(sys.argv[1])
names=[
"frontend.pre-refinement-20260923T145921Z",
"frontend.pre-refinement-20260923T150754Z",
"frontend.pre-neural-safe-20260923T175535Z",
"frontend.pre-connecting-20260923T185145Z",
"frontend.pre-unified-20260923T202118Z",
"frontend.pre-hierarchy-20260923T224239Z",
]
rels=["index.html","static/custom.css","static/loader.js","static/owui-orb-v1.js","static/owui-orb-v1.css"]

def h(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"

present=[n for n in names if (pkg/n).is_dir()]
for a,b in zip(present,present[1:]):
    print(f"PAIR {a} -> {b}")
    for rel in rels:
        ha=h(pkg/a/rel); hb=h(pkg/b/rel)
        print(f"  {rel} changed={'YES' if ha!=hb else 'NO'} a={ha[:16]} b={hb[:16]}")
PY

echo "NEURAL_LINEAGE_FINGERPRINT=END"
echo "RUNTIME_MUTATION=NONE"
