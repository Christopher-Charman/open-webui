#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re

BASE = Path('/home/storage/781/4477781/user/webapp')
PKG = BASE / 'envs/openwebui/lib/python3.11/site-packages/open_webui'

SNAPS = [
    'frontend.pre-neural-safe-20260923T175535Z',
    'frontend.pre-connecting-20260923T185145Z',
    'frontend.pre-unified-20260923T202118Z',
    'frontend.pre-hierarchy-20260923T224239Z',
]

PATTERNS = {
    'SYSTEM_READY': re.compile(r'SYSTEM READY', re.I),
    'READY': re.compile(r'\\bREADY\\b|\\bReady\\b'),
    'CONTINUITY_SHELL': re.compile(r'Continuity Shell', re.I),
    'CONTINUITY_AGENT': re.compile(r'Continuity Agent', re.I),
    'NEURAL': re.compile(r'neural', re.I),
    'SPHERE': re.compile(r'sphere', re.I),
    'BORDER_BEAM': re.compile(r'border[-_ ]?beam|BorderBeam|borderBeam', re.I),
    'GLOW': re.compile(r'glow|bloom', re.I),
    'GOO_METAL': re.compile(r'gooey|goo\\b|metal|sheen|rim', re.I),
    'MESSAGE_INPUT': re.compile(r'message-input-container', re.I),
    'SHELL_STATE': re.compile(r'shellState|continuity.*state|readyState', re.I),
    'CIRCULAR_CONTROL': re.compile(r'rounded-full|border-radius:\\s*9999|border-radius:\\s*50%', re.I),
}

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def app_entry(text: str):
    m = re.search(r'/_app/immutable/entry/(app\\.[A-Za-z0-9_-]+\\.js)', text)
    return m.group(1) if m else None

def immutable_manifest(root: Path):
    out = {}
    if not root.is_dir():
        return out
    for p in root.rglob('*'):
        if p.is_file():
            out[str(p.relative_to(root))] = sha(p)
    return out

print('IMMUTABLE_NEURAL_AUDIT=BEGIN')
print('mode=READ_ONLY')

records = {}
manifests = {}

for name in SNAPS:
    root = PKG / name
    print()
    print(f'===== {name} =====')
    if not root.is_dir():
        print('snapshot=MISSING')
        continue

    idx = root / 'index.html'
    text = idx.read_text(errors='ignore') if idx.is_file() else ''
    entry = app_entry(text)

    print(f'index_sha256={sha(idx) if idx.is_file() else "MISSING"}')
    print(f'app_entry={entry or "MISSING"}')
    if entry:
        ep = root / '_app/immutable/entry' / entry
        print(f'app_entry_exists={"YES" if ep.is_file() else "NO"}')
        if ep.is_file():
            print(f'app_entry_sha256={sha(ep)}')

    hits = []
    imm = root / '_app/immutable'
    if imm.is_dir():
        for p in imm.rglob('*'):
            if not p.is_file() or p.suffix not in {'.js', '.css'}:
                continue
            try:
                s = p.read_text(errors='ignore')
            except Exception:
                continue
            sigs = {}
            score = 0
            for key, rx in PATTERNS.items():
                n = len(rx.findall(s))
                if n:
                    sigs[key] = n
                    score += min(n, 5)
            if sigs:
                hits.append((score, p, sigs, s))

    hits.sort(key=lambda x: (-x[0], str(x[1])))
    print(f'signature_files={len(hits)}')

    sig_manifest = {}
    for score, p, sigs, s in hits[:40]:
        rel = str(p.relative_to(root))
        ph = sha(p)
        sig_manifest[rel] = ph
        print(f'SIGFILE score={score} sha256={ph} path={rel} sigs={json.dumps(sigs, sort_keys=True)}')

        shown = 0
        for term in ['SYSTEM READY', 'Continuity Shell', 'Continuity Agent', 'neural', 'sphere', 'border-beam', 'BorderBeam', 'READY']:
            pos = s.lower().find(term.lower())
            if pos >= 0 and shown < 6:
                lo = max(0, pos - 180)
                hi = min(len(s), pos + 500)
                excerpt = re.sub(r'\\s+', ' ', s[lo:hi])
                print(f'  EXCERPT term={term} text={excerpt[:760]}')
                shown += 1

    records[name] = sig_manifest
    manifests[name] = immutable_manifest(imm)

print()
print('=== CROSS-SNAPSHOT SIGNATURE FILE DELTAS ===')
present = [n for n in SNAPS if n in records]
for a, b in zip(present, present[1:]):
    A, B = records[a], records[b]
    changed = [p for p in sorted(set(A) | set(B)) if A.get(p) != B.get(p)]
    print(f'PAIR {a} -> {b} changed_signature_files={len(changed)}')
    for p in changed[:80]:
        av = A.get(p, 'MISSING')
        bv = B.get(p, 'MISSING')
        print(f'  {p} a={av[:16]} b={bv[:16]}')

print()
print('=== FULL IMMUTABLE MANIFEST DELTAS ===')
for a, b in zip(present, present[1:]):
    A, B = manifests[a], manifests[b]
    changed = [p for p in sorted(set(A) | set(B)) if A.get(p) != B.get(p)]
    print(f'PAIR {a} -> {b} changed_immutable_files={len(changed)}')
    for p in changed[:120]:
        av = A.get(p, 'MISSING')
        bv = B.get(p, 'MISSING')
        print(f'  {p} a={av[:16]} b={bv[:16]}')

print('IMMUTABLE_NEURAL_AUDIT=END')
print('RUNTIME_MUTATION=NONE')
