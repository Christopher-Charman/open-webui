#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib, re

BASE = Path('/home/storage/781/4477781/user/webapp')
PKG = BASE / 'envs/openwebui/lib/python3.11/site-packages/open_webui'

START = datetime(2026,9,23,0,0,tzinfo=timezone.utc).timestamp()
END   = datetime(2026,9,25,0,0,tzinfo=timezone.utc).timestamp()

SIGS = {
    'SYSTEM_READY': re.compile(r'SYSTEM READY', re.I),
    'READY': re.compile(r'\bREADY\b|\bReady\b'),
    'CONTINUITY_SHELL': re.compile(r'Continuity Shell', re.I),
    'CONTINUITY_AGENT': re.compile(r'Continuity Agent', re.I),
    'NEURAL': re.compile(r'neural', re.I),
    'SPHERE': re.compile(r'sphere', re.I),
    'BORDER_BEAM': re.compile(r'border[-_ ]?beam|BorderBeam|borderBeam', re.I),
    'MESSAGE_INPUT': re.compile(r'message-input-container', re.I),
    'THINKING_ORB': re.compile(r'thinking[-_ ]?orb|owui-thinking-orb-v1', re.I),
    'ROUND_CONTROL': re.compile(r'rounded-full|border-radius:\s*(?:9999|50%)', re.I),
    'GOO_METAL': re.compile(r'gooey|goo\b|metal|sheen|rim', re.I),
}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def scan(root):
    totals={k:0 for k in SIGS}
    top=[]
    imm=root/'_app/immutable'
    if not imm.is_dir():
        return totals, top
    for p in imm.rglob('*'):
        if not p.is_file() or p.suffix not in {'.js','.css'}:
            continue
        try:s=p.read_text(errors='ignore')
        except Exception:continue
        found={}
        for k,rx in SIGS.items():
            n=len(rx.findall(s))
            if n:
                totals[k]+=n
                found[k]=n
        if found:
            score=0
            score += min(found.get('NEURAL',0),4)*4
            score += min(found.get('SPHERE',0),4)*4
            score += min(found.get('CONTINUITY_SHELL',0),2)*4
            score += min(found.get('BORDER_BEAM',0),3)*3
            score += min(found.get('MESSAGE_INPUT',0),2)*2
            score += min(found.get('ROUND_CONTROL',0),5)
            score += min(found.get('GOO_METAL',0),4)
            score += min(found.get('READY',0),3)
            score -= min(found.get('SYSTEM_READY',0),4)*5
            top.append((score,p.relative_to(root),sha(p),found,p.stat().st_size))
    top.sort(key=lambda x:(-x[0],str(x[1])))
    return totals,top

snaps=[]
for p in PKG.glob('frontend.pre-*'):
    if not p.is_dir():continue
    ts=p.stat().st_mtime
    if START <= ts < END:
        snaps.append((ts,p))
snaps.sort()

print('NEURAL_TIMELINE_AUDIT=BEGIN')
print('mode=READ_ONLY')
print(f'snapshot_count={len(snaps)}')

for ts,root in snaps:
    dt=datetime.fromtimestamp(ts,timezone.utc).isoformat()
    totals,top=scan(root)
    # Desired screenshot heuristic:
    # neural/sphere/Continuity + READY rewarded; SYSTEM READY strongly penalized.
    score=0
    score += min(totals['NEURAL'],8)*3
    score += min(totals['SPHERE'],8)*3
    score += min(totals['CONTINUITY_SHELL'],4)*5
    score += min(totals['BORDER_BEAM'],6)*3
    score += min(totals['MESSAGE_INPUT'],4)*2
    score += min(totals['ROUND_CONTROL'],10)
    score += min(totals['GOO_METAL'],8)
    score += min(totals['READY'],6)
    score -= min(totals['SYSTEM_READY'],8)*8

    print()
    print(f'SNAPSHOT={root.name}')
    print(f'mtime_utc={dt}')
    print(f'desired_visual_score={score}')
    for k in SIGS:
        print(f'{k}={totals[k]}')
    idx=root/'index.html'
    if idx.is_file():
        print(f'index_sha256={sha(idx)}')
    print('TOP_VISUAL_MODULES:')
    for item in top[:12]:
        sc,rel,h,found,size=item
        print(f'  score={sc} bytes={size} sha256={h} path={rel} markers={found}')

print()
print('=== RANKED CANDIDATES ===')
ranked=[]
for ts,root in snaps:
    totals,top=scan(root)
    score=(min(totals['NEURAL'],8)*3 + min(totals['SPHERE'],8)*3 +
           min(totals['CONTINUITY_SHELL'],4)*5 + min(totals['BORDER_BEAM'],6)*3 +
           min(totals['MESSAGE_INPUT'],4)*2 + min(totals['ROUND_CONTROL'],10) +
           min(totals['GOO_METAL'],8) + min(totals['READY'],6) -
           min(totals['SYSTEM_READY'],8)*8)
    ranked.append((score,ts,root.name,totals))
for score,ts,name,totals in sorted(ranked,reverse=True)[:12]:
    print(f'score={score} snapshot={name} mtime_utc={datetime.fromtimestamp(ts,timezone.utc).isoformat()} SYSTEM_READY={totals["SYSTEM_READY"]} NEURAL={totals["NEURAL"]} SPHERE={totals["SPHERE"]} BORDER_BEAM={totals["BORDER_BEAM"]} CONTINUITY_SHELL={totals["CONTINUITY_SHELL"]}')

print('NEURAL_TIMELINE_AUDIT=END')
print('RUNTIME_MUTATION=NONE')
