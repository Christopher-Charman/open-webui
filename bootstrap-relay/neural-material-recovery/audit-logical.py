#!/usr/bin/env python3
from pathlib import Path
import hashlib, re

BASE = Path('/home/storage/781/4477781/user/webapp')
PKG = BASE / 'envs/openwebui/lib/python3.11/site-packages/open_webui'

SNAPS = [
    'frontend.pre-neural-safe-20260923T175535Z',
    'frontend.pre-connecting-20260923T185145Z',
    'frontend.pre-unified-20260923T202118Z',
    'frontend.pre-hierarchy-20260923T224239Z',
]

TERMS = [
    'SYSTEM READY',
    'Continuity Shell',
    'Continuity Agent',
    'neural',
    'sphere',
    'border-beam',
    'BorderBeam',
    'message-input-container',
    'thinking-orb',
    'READY',
]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def logical_key(rel):
    s = str(rel)
    s = re.sub(r'(entry/(?:app|start))\.[A-Za-z0-9_-]+(\.js)$', r'\1\2', s)
    s = re.sub(r'(nodes/\d+)\.[A-Za-z0-9_-]+(\.js)$', r'\1\2', s)
    s = re.sub(r'((?:chunks|assets)/[^./]+)\.[A-Za-z0-9_-]+(\.(?:js|css))$', r'\1\2', s)
    return s

print('NEURAL_LOGICAL_AUDIT=BEGIN')
print('mode=READ_ONLY')

snapshot_hits = {}

for name in SNAPS:
    root = PKG / name
    print()
    print(f'===== {name} =====')
    if not root.is_dir():
        print('snapshot=MISSING')
        continue

    hits = []
    imm = root / '_app/immutable'
    for p in imm.rglob('*'):
        if not p.is_file() or p.suffix not in {'.js','.css'}:
            continue
        try:
            text = p.read_text(errors='ignore')
        except Exception:
            continue

        found = {}
        for term in TERMS:
            n = text.lower().count(term.lower())
            if n:
                found[term] = n

        # READY alone is noisy. Require one stronger marker, or at least 2 relevant markers.
        strong = any(k in found for k in [
            'SYSTEM READY','Continuity Shell','Continuity Agent','neural',
            'sphere','border-beam','BorderBeam','message-input-container','thinking-orb'
        ])
        if not strong and len(found) < 2:
            continue

        rel = p.relative_to(root)
        hits.append((logical_key(rel), rel, p, text, found))

    hits.sort(key=lambda x:(x[0],str(x[1])))
    snapshot_hits[name] = {}

    for key, rel, p, text, found in hits:
        snapshot_hits[name].setdefault(key, []).append((rel, sha(p), found))
        print(f'LOGICAL={key}')
        print(f'  file={rel}')
        print(f'  sha256={sha(p)}')
        print(f'  bytes={p.stat().st_size}')
        print('  markers=' + ','.join(f'{k}:{v}' for k,v in sorted(found.items())))

        shown = 0
        for term in [
            'SYSTEM READY','Continuity Shell','Continuity Agent',
            'neural','sphere','border-beam','BorderBeam',
            'message-input-container','thinking-orb'
        ]:
            pos = text.lower().find(term.lower())
            if pos >= 0 and shown < 5:
                lo=max(0,pos-180); hi=min(len(text),pos+520)
                ex=re.sub(r'\s+',' ',text[lo:hi])
                print(f'  excerpt[{term}]={ex[:760]}')
                shown += 1
        print()

print('=== LOGICAL MODULE EVOLUTION ===')
keys = sorted(set().union(*(set(v.keys()) for v in snapshot_hits.values())))
for key in keys:
    rows=[]
    for name in SNAPS:
        vals=snapshot_hits.get(name,{}).get(key,[])
        if vals:
            rows.append((name, vals))
    if len(rows) < 2:
        continue
    print(f'MODULE={key}')
    for name,vals in rows:
        desc='; '.join(f'{rel} sha={h[:16]} markers={sorted(m)}' for rel,h,m in vals)
        print(f'  {name}: {desc}')

print('NEURAL_LOGICAL_AUDIT=END')
print('RUNTIME_MUTATION=NONE')
