#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import os
import re
import shutil
import sys
import tempfile
import urllib.request

BASE = Path('/home/storage/781/4477781/user/webapp')
PKG = BASE / 'envs/openwebui/lib/python3.11/site-packages/open_webui'
FRONTEND = PKG / 'frontend'
FRONT_STATIC = FRONTEND / 'static'
SERVED_STATIC = PKG / 'static'
INDEX = FRONTEND / 'index.html'
ASSET_PIN = 'c28c8ccec5bc551742b8fdbd0217b373faac3586'
ASSET_BASE = f'https://raw.githubusercontent.com/Christopher-Charman/open-webui/{ASSET_PIN}/bootstrap-relay/pwa-lkg-1956/assets'
CACHE_GEN = '20260929-lkg1956-r1'
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
BACKUP = BASE / 'runtime-domains/pwa-repair-agent/backups' / f'lkg1956-restore-{STAMP}'

ASSETS = {
    'loader.js': {
        'blob': 'e030f5c57eb039daddc44309c3fbc136fc48f9a7',
        'sha256': 'e101590a26011b7d804470936333075dc97c20131e7d70bffd889754b35e2f39',
    },
    'custom.css': {
        'blob': '8825ef3d2148fc5994e4d1c5ee910aebe9396223',
        'sha256': '475abc34859bc632461e6bd66bef2e2893fdc8e108035ce5a0617461a6469484',
    },
    'pwa-voice-bridge.js': {
        'blob': '18689a3c598903d262f5e463a6bb0b3aa531af41',
        'sha256': 'ad38be628a364e50f4f495970b0c2381bc10ac2f64e3acf8bf8f0313fa14b0f6',
    },
    'pwa-client-runtime.js': {'blob': '6fba22fa006f78d1c4c8e2ee0d1025c6f3d68d01'},
    'lcars-runtime.js': {'blob': '44606bf8dcc9cd2aae82fe76cbbe2f003b530cc6'},
    'lcars-theme.css': {'blob': '04448d8109a9aa066a8321fecabfda11388f73fa'},
    'continuity-shell-registry.js': {'blob': 'e5b6e65bd723ff04f027b5d2762db4bbd537aec3'},
    'continuity-settings.js': {'blob': '3711df4d5c94c3e2334824b3e4f4b097a8fb079e'},
    'site.webmanifest': {'blob': 'ae6109ac991db51885c9ad2fe0590802d9e953d3'},
}

POST_ISOLATION_DIRECT_SCRIPTS = (
    'pwa-client-runtime.js',
    'pwa-voice-bridge.js',
    'lcars-runtime.js',
    'continuity-shell-registry.js',
    'continuity-controls.js',
    'continuity-settings.js',
)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def git_blob_sha1(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(f'blob {len(data)}\0'.encode())
    h.update(data)
    return h.hexdigest()

def fetch_asset(name: str) -> bytes:
    req = urllib.request.Request(
        f'{ASSET_BASE}/{name}',
        headers={'User-Agent': 'powerpc-darwin-lkg1956-recovery/1.0', 'Cache-Control': 'no-cache'}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def runtime_bytes(name: str, data: bytes, meta: dict) -> bytes:
    """Preserve Git identity, then normalize only a single terminal newline when
    required to reproduce the archived live-runtime SHA-256."""
    expected = meta.get('sha256')
    if not expected:
        return data
    if sha256_bytes(data) == expected:
        return data

    candidates = []
    if data.endswith(b'\r\n'):
        candidates.append(data[:-2])
    elif data.endswith(b'\n'):
        candidates.append(data[:-1])
    else:
        candidates.append(data + b'\n')

    for candidate in candidates:
        if sha256_bytes(candidate) == expected:
            print(f'NORMALIZED_TRAILING_NEWLINE={name}')
            return candidate

    raise SystemExit(
        f'ERROR historical runtime sha256 mismatch after bounded newline normalization: {name}'
    )

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

def backup_file(path: Path, rel: str):
    if path.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)

def restore_backup():
    try:
        idx = BACKUP / 'frontend/index.html'
        if idx.exists():
            shutil.copy2(idx, INDEX)
        for name in set(ASSETS) | {'continuity-controls.js'}:
            for root, relroot in ((FRONT_STATIC, 'frontend/static'), (SERVED_STATIC, 'served/static')):
                src = BACKUP / relroot / name
                if src.exists():
                    shutil.copy2(src, root / name)
        print('ROLLBACK=AUTO_RESTORED')
    except Exception as e:
        print(f'ROLLBACK=FAILED error={e}')

if not INDEX.exists():
    raise SystemExit(f'ERROR index missing: {INDEX}')
if not FRONT_STATIC.exists() or not SERVED_STATIC.exists():
    raise SystemExit('ERROR expected OpenWebUI static directories missing')

downloaded = {}
for name, meta in ASSETS.items():
    source_data = fetch_asset(name)
    if git_blob_sha1(source_data) != meta['blob']:
        raise SystemExit(f'ERROR source blob mismatch: {name}')
    downloaded[name] = runtime_bytes(name, source_data, meta)

index_text = INDEX.read_text()

# Remove only the two later experimental inline PWA guards.
index_text = re.sub(
    r'\s*<script id="owui-pwa-legacy-chats-bypass-v20260929\.5">.*?</script>',
    '',
    index_text,
    count=1,
    flags=re.S,
)
index_text = re.sub(
    r'\s*<script id="owui-pwa-startup-guard-v20260929\.6">.*?</script>',
    '',
    index_text,
    count=1,
    flags=re.S,
)

# Return SvelteKit to the stock 0.11.3 immutable entrypoints. Keep generated .6 files
# on disk as evidence/rollback material; simply stop referencing them.
index_text = re.sub(
    r'(app\.[A-Za-z0-9_-]+)\.pwa20260929_6\.js',
    r'\1.js',
    index_text,
)
index_text = re.sub(
    r'(2\.[A-Za-z0-9_-]+)\.pwa20260929_6\.js',
    r'\1.js',
    index_text,
)

# Re-establish the 19:56 bootstrap-isolation boundary: loader owns bootstrap and the
# later direct client/voice/LCARS injections are not allowed to race stock Svelte mount.
for name in POST_ISOLATION_DIRECT_SCRIPTS:
    pat = rf'\s*<script\b(?=[^>]*\bsrc=["\'][^"\']*/static/{re.escape(name)}(?:\?[^"\']*)?["\'])[^>]*>\s*</script>'
    index_text = re.sub(pat, '', index_text, flags=re.I)

# Force a genuinely new cache identity. This is the historically proven repair mechanism:
# changing server bytes without changing the loader URL was insufficient on iOS.
loader_pat = r'(<script\b[^>]*\bsrc=["\'])/static/loader\.js(?:\?[^"\']*)?(["\'][^>]*>\s*</script>)'
if not re.search(loader_pat, index_text, flags=re.I):
    raise SystemExit('ERROR loader script tag missing')
index_text = re.sub(
    loader_pat,
    rf'\1/static/loader.js?v={CACHE_GEN}\2',
    index_text,
    count=1,
    flags=re.I,
)

css_pat = r'(<link\b[^>]*\bhref=["\'])/static/custom\.css(?:\?[^"\']*)?(["\'][^>]*>)'
if not re.search(css_pat, index_text, flags=re.I):
    raise SystemExit('ERROR custom.css link tag missing')
index_text = re.sub(
    css_pat,
    rf'\1/static/custom.css?v={CACHE_GEN}\2',
    index_text,
    count=1,
    flags=re.I,
)

# Pre-write invariants.
if 'owui-pwa-legacy-chats-bypass-v20260929.5' in index_text:
    raise SystemExit('ERROR .5 guard remains in prepared index')
if 'owui-pwa-startup-guard-v20260929.6' in index_text:
    raise SystemExit('ERROR .6 guard remains in prepared index')
if '.pwa20260929_6.js' in index_text:
    raise SystemExit('ERROR .6 immutable entry reference remains in prepared index')
for name in POST_ISOLATION_DIRECT_SCRIPTS:
    if re.search(rf'<script\b[^>]*\bsrc=["\'][^"\']*/static/{re.escape(name)}(?:\?[^"\']*)?["\']', index_text, flags=re.I):
        raise SystemExit(f'ERROR direct post-isolation script remains: {name}')
if f'/static/loader.js?v={CACHE_GEN}' not in index_text:
    raise SystemExit('ERROR fresh loader generation missing from prepared index')
if f'/static/custom.css?v={CACHE_GEN}' not in index_text:
    raise SystemExit('ERROR fresh CSS generation missing from prepared index')

# Preserve exact current state before mutation.
BACKUP.mkdir(parents=True, exist_ok=False)
backup_file(INDEX, 'frontend/index.html')
for name in set(ASSETS) | {'continuity-controls.js'}:
    backup_file(FRONT_STATIC / name, f'frontend/static/{name}')
    backup_file(SERVED_STATIC / name, f'served/static/{name}')

try:
    # Restore exact known-good client bytes to both source/build and currently served trees.
    for name, data in downloaded.items():
        atomic_write(FRONT_STATIC / name, data)
        atomic_write(SERVED_STATIC / name, data)
    atomic_write(INDEX, index_text.encode())

    # On-disk verification before lifecycle action.
    # Source provenance was already verified against the Git blob before normalization.
    # Runtime bytes are authoritative here: assets with an archived live SHA must match
    # that exact SHA; assets without one remain byte-identical to the Git source blob.
    for name, meta in ASSETS.items():
        for root in (FRONT_STATIC, SERVED_STATIC):
            data = (root / name).read_bytes()
            if meta.get('sha256'):
                if sha256_bytes(data) != meta['sha256']:
                    raise RuntimeError(f'postwrite runtime sha256 mismatch: {root / name}')
            elif git_blob_sha1(data) != meta['blob']:
                raise RuntimeError(f'postwrite source blob mismatch: {root / name}')

    written = INDEX.read_text()
    if f'/static/loader.js?v={CACHE_GEN}' not in written:
        raise RuntimeError('postwrite loader generation missing')
    if f'/static/custom.css?v={CACHE_GEN}' not in written:
        raise RuntimeError('postwrite custom.css generation missing')
    if '.pwa20260929_6.js' in written:
        raise RuntimeError('postwrite .6 entry reference remains')
    if 'owui-pwa-legacy-chats-bypass-v20260929.5' in written or 'owui-pwa-startup-guard-v20260929.6' in written:
        raise RuntimeError('postwrite experimental PWA guard remains')
except Exception:
    restore_backup()
    raise

receipt = BACKUP / 'RESTORE_RECEIPT.txt'
receipt.write_text(
    '\n'.join([
        'LKG_1956=STAGED_ON_DISK',
        f'cache_generation={CACHE_GEN}',
        f'asset_pin={ASSET_PIN}',
        f'backup={BACKUP}',
        'loader_sha256=' + sha256_bytes((FRONT_STATIC / 'loader.js').read_bytes()),
        'custom_css_sha256=' + sha256_bytes((FRONT_STATIC / 'custom.css').read_bytes()),
        'voice_bridge_sha256=' + sha256_bytes((FRONT_STATIC / 'pwa-voice-bridge.js').read_bytes()),
        'stock_svelte_entry=RESTORED',
        'post_isolation_direct_scripts=REMOVED_FROM_INDEX',
        'experimental_pwa_guards=REMOVED',
        '',
    ])
)

print('LKG_1956=STAGED_ON_DISK')
print(f'cache_generation={CACHE_GEN}')
print(f'backup={BACKUP}')
print('loader_sha256=' + sha256_bytes((FRONT_STATIC / 'loader.js').read_bytes()))
print('custom_css_sha256=' + sha256_bytes((FRONT_STATIC / 'custom.css').read_bytes()))
print('voice_bridge_sha256=' + sha256_bytes((FRONT_STATIC / 'pwa-voice-bridge.js').read_bytes()))
print('NEXT=PASSENGER_RESTART_AND_PUBLIC_VERIFY')
