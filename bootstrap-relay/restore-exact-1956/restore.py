#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib, os, re, shutil, sys, tempfile, urllib.request

BASE = Path('/home/storage/781/4477781/user/webapp')
PKG = BASE / 'envs/openwebui/lib/python3.11/site-packages/open_webui'
FRONTEND = PKG / 'frontend'
FRONT_STATIC = FRONTEND / 'static'
SERVED_STATIC = PKG / 'static'
INDEX = FRONTEND / 'index.html'
CHECKPOINT = BASE / 'checkpoints/openwebui-spinner-repair-20260928-2105'
RESTART = BASE / 'restart-openwebui-via-passenger.sh'

ASSET_PIN = 'c28c8ccec5bc551742b8fdbd0217b373faac3586'
ASSET_BASE = f'https://raw.githubusercontent.com/Christopher-Charman/open-webui/{ASSET_PIN}/bootstrap-relay/pwa-lkg-1956/assets'
CACHE_GEN = 'restore-1956-20260929-r2'
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
BACKUP = BASE / 'runtime-domains/pwa-repair-agent/backups' / f'pre-exact-1956-{STAMP}'

ASSETS = {
    'loader.js': 'e101590a26011b7d804470936333075dc97c20131e7d70bffd889754b35e2f39',
    'custom.css': '475abc34859bc632461e6bd66bef2e2893fdc8e108035ce5a0617461a6469484',
    'pwa-voice-bridge.js': 'ad38be628a364e50f4f495970b0c2381bc10ac2f64e3acf8bf8f0313fa14b0f6',
    'pwa-client-runtime.js': None,
    'lcars-runtime.js': None,
    'lcars-theme.css': None,
    'continuity-shell-registry.js': None,
    'continuity-settings.js': None,
    'site.webmanifest': None,
}

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def fetch(name):
    req = urllib.request.Request(
        f'{ASSET_BASE}/{name}',
        headers={'User-Agent':'owui-1956-restore/2','Cache-Control':'no-cache'}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def normalize_historical(name, data, expected):
    if not expected or sha256(data) == expected:
        return data
    for candidate in (
        data[:-2] if data.endswith(b'\r\n') else None,
        data[:-1] if data.endswith(b'\n') else None,
        data + b'\n' if not data.endswith(b'\n') else None,
    ):
        if candidate is not None and sha256(candidate) == expected:
            print(f'NORMALIZED_TRAILING_NEWLINE={name}')
            return candidate
    raise SystemExit(f'ERROR cannot reproduce recorded 19:56 sha256 for {name}')

def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def copy_if_exists(src, dst):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

if not CHECKPOINT.is_dir():
    raise SystemExit(f'ERROR checkpoint missing: {CHECKPOINT}')

index_candidates = [p for p in CHECKPOINT.rglob('index.html') if p.is_file()]
if len(index_candidates) != 1:
    raise SystemExit('ERROR expected exactly one checkpoint index.html; found ' + str(len(index_candidates)))
checkpoint_index = index_candidates[0]

# Fetch exact Git-backed 19:56 assets and reproduce the recorded live representation.
downloaded = {}
for name, expected in ASSETS.items():
    data = fetch(name)
    data = normalize_historical(name, data, expected)
    downloaded[name] = data

# Prepare the preserved checkpoint document. Only cache-addressing is changed.
index_text = checkpoint_index.read_text()

# Strip later 29-Sep experiments if a checkpoint copy was subsequently contaminated.
index_text = re.sub(r'\s*<script id="owui-pwa-legacy-chats-bypass-v20260929\.5">.*?</script>', '', index_text, flags=re.S)
index_text = re.sub(r'\s*<script id="owui-pwa-startup-guard-v20260929\.6">.*?</script>', '', index_text, flags=re.S)
index_text = re.sub(r'(app\.[A-Za-z0-9_-]+)\.pwa20260929_6\.js', r'\1.js', index_text)
index_text = re.sub(r'(2\.[A-Za-z0-9_-]+)\.pwa20260929_6\.js', r'\1.js', index_text)

# Preserve the checkpoint's script topology, but issue a brand-new cache identity
# for all custom static JS/CSS references so iOS/Safari cannot serve later bytes.
def bust(m):
    return f'{m.group(1)}?v={CACHE_GEN}'

index_text = re.sub(
    r'(/static/(?:loader|custom|pwa-voice-bridge|pwa-client-runtime|lcars-runtime|lcars-theme|continuity-shell-registry|continuity-settings)\.(?:js|css))(?:\?[^"\']*)?',
    bust,
    index_text
)

marker = f'<!-- owui-exact-1956-restore:{CACHE_GEN} -->'
index_text = re.sub(r'\s*<!-- owui-exact-1956-restore:[^>]*-->', '', index_text)
if '</head>' not in index_text:
    raise SystemExit('ERROR checkpoint index lacks </head>')
index_text = index_text.replace('</head>', f'\n\t\t{marker}\n\t</head>', 1)

# Reject post-checkpoint experimental references.
for bad in (
    'owui-pwa-legacy-chats-bypass-v20260929.5',
    'owui-pwa-startup-guard-v20260929.6',
    '.pwa20260929_6.js',
):
    if bad in index_text:
        raise SystemExit(f'ERROR post-checkpoint residue remains: {bad}')

# Snapshot current live client boundary.
BACKUP.mkdir(parents=True, exist_ok=False)
copy_if_exists(INDEX, BACKUP/'frontend/index.html')
for name in set(ASSETS) | {'continuity-controls.js'}:
    copy_if_exists(FRONT_STATIC/name, BACKUP/'frontend/static'/name)
    copy_if_exists(SERVED_STATIC/name, BACKUP/'served/static'/name)

try:
    # Restore the actual checkpoint document and validated static bytes.
    atomic_write(INDEX, index_text.encode())
    for name, data in downloaded.items():
        atomic_write(FRONT_STATIC/name, data)
        atomic_write(SERVED_STATIC/name, data)

    # Validate the three human-checkpointed hashes exactly.
    for name, expected in ASSETS.items():
        if expected:
            for root in (FRONT_STATIC, SERVED_STATIC):
                got = sha256((root/name).read_bytes())
                if got != expected:
                    raise RuntimeError(f'{name} runtime sha mismatch at {root}: {got}')

    written = INDEX.read_text()
    if marker not in written:
        raise RuntimeError('restore marker missing')
    if f'/static/loader.js?v={CACHE_GEN}' not in written:
        raise RuntimeError('fresh loader cache identity missing')
    if f'/static/custom.css?v={CACHE_GEN}' not in written:
        raise RuntimeError('fresh custom.css cache identity missing')

except Exception:
    copy_if_exists(BACKUP/'frontend/index.html', INDEX)
    for name in set(ASSETS) | {'continuity-controls.js'}:
        copy_if_exists(BACKUP/'frontend/static'/name, FRONT_STATIC/name)
        copy_if_exists(BACKUP/'served/static'/name, SERVED_STATIC/name)
    print('RESTORE_1956=ROLLBACK_AUTO_RESTORED')
    raise

receipt = BACKUP/'RESTORE_1956_RECEIPT.txt'
receipt.write_text('\n'.join([
    'RESTORE_1956=STAGED',
    f'checkpoint_index={checkpoint_index}',
    f'cache_generation={CACHE_GEN}',
    f'backup={BACKUP}',
    'loader_sha256='+sha256((FRONT_STATIC/'loader.js').read_bytes()),
    'custom_css_sha256='+sha256((FRONT_STATIC/'custom.css').read_bytes()),
    'voice_bridge_sha256='+sha256((FRONT_STATIC/'pwa-voice-bridge.js').read_bytes()),
    '',
]))

print('RESTORE_1956=STAGED')
print(f'checkpoint_index={checkpoint_index}')
print(f'cache_generation={CACHE_GEN}')
print(f'backup={BACKUP}')
print('loader_sha256='+sha256((FRONT_STATIC/'loader.js').read_bytes()))
print('custom_css_sha256='+sha256((FRONT_STATIC/'custom.css').read_bytes()))
print('voice_bridge_sha256='+sha256((FRONT_STATIC/'pwa-voice-bridge.js').read_bytes()))
print('NEXT=RESTART_AND_PUBLIC_VERIFY')
