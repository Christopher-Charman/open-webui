#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

BASE = Path('/home/storage/781/4477781/user/webapp')
PKG = BASE / 'envs/openwebui/lib/python3.11/site-packages/open_webui'
FRONTEND = PKG / 'frontend'
FRONT_STATIC = FRONTEND / 'static'
SERVED_STATIC = PKG / 'static'
INDEX = FRONTEND / 'index.html'
STATE_DIR = BASE / 'runtime-domains/pwa-repair-agent'
STATE = STATE_DIR / 'backup-bisect-state.json'
PRE_ROOT = STATE_DIR / 'backups'
CUTOFF = 20260929000000  # skip the already-failed 29 Sep experiment lineage

CLIENT_ASSETS = (
    'loader.js',
    'custom.css',
    'pwa-voice-bridge.js',
    'pwa-client-runtime.js',
    'lcars-runtime.js',
    'lcars-theme.css',
    'continuity-shell-registry.js',
    'continuity-controls.js',
    'continuity-settings.js',
    'owui-orb-v1.js',
    'owui-orb-v1.css',
)

EXCLUDE_FRAGMENTS = (
    'rollback-bisect-prestep-',
    'lkg1956-restore-',
    'pwa20260929',
)

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass

def parse_key(name: str):
    patterns = (
        r'(20\d{6})T(\d{6})Z?',
        r'(20\d{6})[-_](\d{4})(?:\d{2})?',
        r'(20\d{6})(\d{6})',
    )
    for pat in patterns:
        m = re.search(pat, name)
        if m:
            date, time = m.group(1), m.group(2)
            if len(time) == 4:
                time += '00'
            return int(date + time)
    return None

def load_state():
    if not STATE.exists():
        return {'attempted': [], 'last_key': None, 'pending': None}
    try:
        data = json.loads(STATE.read_text())
        data.setdefault('attempted', [])
        data.setdefault('last_key', None)
        data.setdefault('pending', None)
        return data
    except Exception:
        raise SystemExit(f'ERROR invalid bisect state: {STATE}')

def save_state(data):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write(STATE, (json.dumps(data, indent=2, sort_keys=True) + '\n').encode())

def candidate_dirs():
    found = set()

    checkpoints = BASE / 'checkpoints'
    if checkpoints.exists():
        for p in checkpoints.iterdir():
            if p.is_dir():
                found.add(p)

    pwa_backups = STATE_DIR / 'backups'
    if pwa_backups.exists():
        for p in pwa_backups.iterdir():
            if p.is_dir():
                found.add(p)

    for p in PKG.glob('*backups*'):
        if p.is_dir():
            found.add(p)
    for p in PKG.glob('*backup*'):
        if p.is_dir():
            found.add(p)

    out = []
    for p in found:
        s = str(p)
        if any(x in s for x in EXCLUDE_FRAGMENTS):
            continue
        key = parse_key(p.name)
        if key is None or key >= CUTOFF:
            continue
        exact_index = list(p.rglob('index.html'))
        if not exact_index:
            continue
        has_client = any(list(p.rglob(name)) for name in CLIENT_ASSETS)
        # The documented 2026-09-28 spinner-repair checkpoint may contain only the
        # pre-cache-generation index plus control-state material. It is still a valid
        # first rollback boundary when combined with the already-restored 19:56 client bytes.
        known_index_boundary = 'openwebui-spinner-repair-20260928-2105' in p.name
        if not has_client and not known_index_boundary:
            continue
        out.append((key, p))
    out.sort(key=lambda x: (x[0], str(x[1])), reverse=True)
    return out

def choose_exact_file(root: Path, basename: str, prefer_frontend=False):
    matches = [p for p in root.rglob(basename) if p.is_file()]
    if not matches:
        return None

    if prefer_frontend:
        preferred = [p for p in matches if 'frontend' in p.parts]
        if preferred:
            matches = preferred

    if len(matches) == 1:
        return matches[0]

    hashes = {}
    for p in matches:
        hashes.setdefault(sha256(p), []).append(p)
    if len(hashes) == 1:
        return sorted(matches, key=lambda p: (len(p.parts), str(p)))[0]

    raise RuntimeError(
        f'ambiguous backup file {basename}: ' +
        ', '.join(str(p.relative_to(root)) for p in matches)
    )

def snapshot_current(tag: str):
    dst = PRE_ROOT / f'rollback-bisect-prestep-{tag}'
    dst.mkdir(parents=True, exist_ok=False)
    if INDEX.exists():
        d = dst / 'frontend/index.html'
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(INDEX, d)
    for name in CLIENT_ASSETS:
        for srcroot, relroot in ((FRONT_STATIC, 'frontend/static'), (SERVED_STATIC, 'served/static')):
            src = srcroot / name
            if src.exists():
                d = dst / relroot / name
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, d)
    return dst

def restore_prestep(dst: Path):
    src = dst / 'frontend/index.html'
    if src.exists():
        shutil.copy2(src, INDEX)
    for name in CLIENT_ASSETS:
        for targetroot, relroot in ((FRONT_STATIC, 'frontend/static'), (SERVED_STATIC, 'served/static')):
            s = dst / relroot / name
            if s.exists():
                shutil.copy2(s, targetroot / name)

def cache_bust(index_text: str, tag: str):
    # Remove only prior bisect marker comments.
    index_text = re.sub(r'\s*<!-- owui-backup-bisect:[^>]*-->', '', index_text)
    marker = f'<!-- owui-backup-bisect:{tag} -->'
    if '</head>' not in index_text:
        raise RuntimeError('restored index lacks </head> marker')
    index_text = index_text.replace('</head>', f'\n\t\t{marker}\n\t</head>', 1)

    # Force Safari/PWA to fetch restored custom client assets instead of retaining stale bytes.
    def repl(m):
        return f'{m.group(1)}?rb={tag}'
    index_text = re.sub(
        r'(/static/[^"\'?]+\.(?:js|css))(?:\?[^"\']*)?',
        repl,
        index_text,
        flags=re.I,
    )
    return index_text, marker

def apply_next():
    state = load_state()
    if state.get('pending'):
        raise SystemExit('ERROR pending rollback step exists; run wrapper recovery/finalize first')

    candidates = candidate_dirs()
    attempted = set(state.get('attempted', []))
    last_key = state.get('last_key')

    selected = None
    for key, path in candidates:
        sid = str(path)
        if sid in attempted:
            continue
        if last_key is not None and key >= int(last_key):
            continue
        selected = (key, path)
        break

    if selected is None:
        print('BACKUP_BISECT=EXHAUSTED')
        print('DISCOVERED=' + str(len(candidates)))
        for key, path in candidates:
            print(f'CANDIDATE key={key} path={path}')
        raise SystemExit(3)

    key, root = selected
    index_src = choose_exact_file(root, 'index.html', prefer_frontend=True)
    if not index_src:
        raise SystemExit(f'ERROR selected snapshot has no exact index.html: {root}')

    tag = f'{key}-{hashlib.sha256(str(root).encode()).hexdigest()[:8]}'
    prestep = snapshot_current(tag)

    restored = []
    try:
        shutil.copy2(index_src, INDEX)
        restored.append(('index.html', str(index_src.relative_to(root)), sha256(INDEX)))

        for name in CLIENT_ASSETS:
            src = choose_exact_file(root, name, prefer_frontend=True)
            if src is None:
                continue
            data = src.read_bytes()
            atomic_write(FRONT_STATIC / name, data)
            atomic_write(SERVED_STATIC / name, data)
            restored.append((name, str(src.relative_to(root)), hashlib.sha256(data).hexdigest()))

        text, marker = cache_bust(INDEX.read_text(), tag)
        atomic_write(INDEX, text.encode())

        # Require the restored index to be the one now on disk and marker to survive.
        written = INDEX.read_text()
        if marker not in written:
            raise RuntimeError('bisect marker missing after write')

        pending = {
            'candidate': str(root),
            'key': key,
            'tag': tag,
            'prestep': str(prestep),
            'restored': [
                {'name': n, 'source': s, 'sha256': h} for n, s, h in restored
            ],
            'started_at': datetime.now(timezone.utc).isoformat(),
        }
        state['pending'] = pending
        save_state(state)

        print('BACKUP_BISECT=STAGED')
        print(f'CANDIDATE={root}')
        print(f'KEY={key}')
        print(f'TAG={tag}')
        print(f'PRESTEP={prestep}')
        print(f'INDEX_SOURCE={index_src}')
        for n, s, h in restored:
            print(f'RESTORED name={n} source={s} sha256={h}')
        print('NEXT=RESTART_PUBLIC_VERIFY')
    except Exception:
        restore_prestep(prestep)
        raise

def commit_pending():
    state = load_state()
    p = state.get('pending')
    if not p:
        raise SystemExit('ERROR no pending rollback step')
    attempted = state.setdefault('attempted', [])
    if p['candidate'] not in attempted:
        attempted.append(p['candidate'])
    state['last_key'] = p['key']
    state['last_successful_host_step'] = p
    state['pending'] = None
    save_state(state)
    print('BACKUP_BISECT=HOST_PASS_COMMITTED')
    print(f'CANDIDATE={p["candidate"]}')
    print(f'KEY={p["key"]}')
    print(f'TAG={p["tag"]}')

def abort_pending():
    state = load_state()
    p = state.get('pending')
    if not p:
        print('BACKUP_BISECT=NO_PENDING')
        return
    prestep = Path(p['prestep'])
    restore_prestep(prestep)
    state['pending'] = None
    save_state(state)
    print('BACKUP_BISECT=ABORT_RESTORED_PRESTEP')
    print(f'PRESTEP={prestep}')

def status():
    state = load_state()
    print(json.dumps(state, indent=2, sort_keys=True))
    for key, p in candidate_dirs():
        print(f'CANDIDATE key={key} path={p}')

cmd = sys.argv[1] if len(sys.argv) > 1 else '--next'
if cmd == '--next':
    apply_next()
elif cmd == '--commit':
    commit_pending()
elif cmd == '--abort':
    abort_pending()
elif cmd == '--status':
    status()
else:
    raise SystemExit('usage: backup_stepper.py [--next|--commit|--abort|--status]')
