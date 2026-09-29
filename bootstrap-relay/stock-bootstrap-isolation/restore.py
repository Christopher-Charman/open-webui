#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import tempfile

BASE = Path('/home/storage/781/4477781/user/webapp')
PKG = BASE / 'envs/openwebui/lib/python3.11/site-packages/open_webui'
FRONTEND = PKG / 'frontend'
FRONT_STATIC = FRONTEND / 'static'
SERVED_STATIC = PKG / 'static'
INDEX = FRONTEND / 'index.html'
ENTRY_DIR = FRONTEND / '_app/immutable/entry'
NODE_DIR = FRONTEND / '_app/immutable/nodes'
BACKUP_ROOT = BASE / 'runtime-domains/pwa-repair-agent/backups'

STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
CACHE_GEN = 'stock-bootstrap-20260929.1'
MARKER = 'owui-stock-bootstrap-isolation-v20260929.1'
BACKUP = BACKUP_ROOT / f'pre-stock-bootstrap-isolation-{STAMP}'

KNOWN_CUSTOM_STATIC = (
    'pwa-client-runtime.js',
    'pwa-voice-bridge.js',
    'lcars-runtime.js',
    'lcars-theme.css',
    'continuity-shell-registry.js',
    'continuity-controls.js',
    'continuity-settings.js',
    'owui-orb-v1.js',
    'owui-orb-v1.css',
    'owui-border-beam-v1.js',
    'owui-border-beam-v1.css',
)

KNOWN_CUSTOM_PREFIXES = (
    'pwa-',
    'lcars-',
    'continuity-',
    'owui-orb',
    'owui-border-beam',
)

INLINE_ID_PREFIXES = (
    'owui-',
    'pwa-',
    'lcars-',
    'continuity-',
)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def atomic_write_bytes(path: Path, data: bytes):
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

def atomic_write_text(path: Path, text: str):
    atomic_write_bytes(path, text.encode())

def backup_file(src: Path, rel: str):
    if not src.exists():
        return
    dst = BACKUP / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

def restore_backup():
    idx = BACKUP / 'frontend/index.html'
    if idx.exists():
        shutil.copy2(idx, INDEX)
    for name in ('loader.js', 'custom.css') + KNOWN_CUSTOM_STATIC:
        for dstroot, relroot in ((FRONT_STATIC, 'frontend/static'), (SERVED_STATIC, 'served/static')):
            src = BACKUP / relroot / name
            if src.exists():
                shutil.copy2(src, dstroot / name)
    print('STOCK_BOOTSTRAP=ROLLBACK_AUTO_RESTORED')

def stock_js_name(path: Path, prefix: str) -> bool:
    return bool(re.fullmatch(rf'{re.escape(prefix)}\.[A-Za-z0-9_-]+\.js', path.name))

if not INDEX.is_file():
    raise SystemExit(f'ERROR index missing: {INDEX}')
if not ENTRY_DIR.is_dir() or not NODE_DIR.is_dir():
    raise SystemExit('ERROR immutable bundle directories missing')

index_text = INDEX.read_text()

# Discover a coherent stock OpenWebUI app/node pair from the installed immutable tree.
# Prefer the 0.11.3 app-layout node identified by the legacy Chats code because this
# distinguishes stock OpenWebUI from our generated clone assets.
node_candidates = []
for path in sorted(NODE_DIR.glob('2.*.js')):
    if not path.is_file() or not stock_js_name(path, '2'):
        continue
    try:
        text = path.read_text()
    except Exception:
        continue
    if 'checkLocalDBChats' in text and re.search(r'openDB\(["\']Chats["\']\s*,\s*1\)', text):
        node_candidates.append((path, text))

if len(node_candidates) != 1:
    print('STOCK_NODE_CANDIDATES=' + str(len(node_candidates)))
    for p, _ in node_candidates:
        print('STOCK_NODE_CANDIDATE=' + str(p))
    raise SystemExit('ERROR cannot uniquely identify stock OpenWebUI 0.11.3 app-layout node')

stock_node_path, stock_node_text = node_candidates[0]
stock_node_name = stock_node_path.name
node_rel = '../nodes/' + stock_node_name

app_candidates = []
for path in sorted(ENTRY_DIR.glob('app.*.js')):
    if not path.is_file() or not stock_js_name(path, 'app'):
        continue
    try:
        text = path.read_text()
    except Exception:
        continue
    if node_rel in text:
        app_candidates.append((path, text))

if len(app_candidates) != 1:
    print('STOCK_APP_CANDIDATES=' + str(len(app_candidates)))
    for p, _ in app_candidates:
        print('STOCK_APP_CANDIDATE=' + str(p))
    raise SystemExit('ERROR cannot uniquely identify coherent stock OpenWebUI app entry')

stock_app_path, stock_app_text = app_candidates[0]
stock_app_name = stock_app_path.name

# Snapshot the exact current client boundary before any write.
BACKUP.mkdir(parents=True, exist_ok=False)
backup_file(INDEX, 'frontend/index.html')
for name in ('loader.js', 'custom.css') + KNOWN_CUSTOM_STATIC:
    backup_file(FRONT_STATIC / name, f'frontend/static/{name}')
    backup_file(SERVED_STATIC / name, f'served/static/{name}')

try:
    # 1) Restore OpenWebUI's own extension points to inert stock semantics.
    atomic_write_bytes(FRONT_STATIC / 'loader.js', b'')
    atomic_write_bytes(SERVED_STATIC / 'loader.js', b'')
    atomic_write_bytes(FRONT_STATIC / 'custom.css', b'')
    atomic_write_bytes(SERVED_STATIC / 'custom.css', b'')

    # 2) Remove known direct custom script/link injection from the document only.
    # Assets/backends stay on disk and are not deleted.
    for name in KNOWN_CUSTOM_STATIC:
        esc = re.escape(name)
        index_text = re.sub(
            rf'\s*<script\b(?=[^>]*\bsrc=["\'][^"\']*/static/{esc}(?:\?[^"\']*)?["\'])[^>]*>\s*</script>',
            '',
            index_text,
            flags=re.I,
        )
        index_text = re.sub(
            rf'\s*<link\b(?=[^>]*\bhref=["\'][^"\']*/static/{esc}(?:\?[^"\']*)?["\'])[^>]*>',
            '',
            index_text,
            flags=re.I,
        )

    # Remove marked inline bootstrap experiments/custom guards, but not arbitrary
    # OpenWebUI inline code.
    def drop_inline_script(m):
        attrs = m.group(1)
        mid = re.search(r'\bid=["\']([^"\']+)["\']', attrs, re.I)
        if mid and mid.group(1).startswith(INLINE_ID_PREFIXES):
            return ''
        return m.group(0)

    index_text = re.sub(
        r'\s*<script\b([^>]*)>.*?</script>',
        drop_inline_script,
        index_text,
        flags=re.S | re.I,
    )

    # Remove our non-executable diagnostic/backport markers.
    index_text = re.sub(r'\s*<!--\s*owui-[^>]*-->', '', index_text, flags=re.I)

    # 3) Repoint the SvelteKit document to the coherent stock immutable app/node pair.
    app_m = re.search(r'/_app/immutable/entry/(app\.[^"\']+\.js)', index_text)
    if not app_m:
        raise RuntimeError('active app entry URL missing from index')
    active_app = app_m.group(1)
    index_text = index_text[:app_m.start()] + '/_app/immutable/entry/' + stock_app_name + index_text[app_m.end():]

    for node_ref in set(re.findall(r'/_app/immutable/nodes/(2\.[^"\']+\.js)', index_text)):
        if node_ref != stock_node_name:
            index_text = index_text.replace(
                '/_app/immutable/nodes/' + node_ref,
                '/_app/immutable/nodes/' + stock_node_name
            )

    # 4) Keep stock loader/custom.css tags, but force new cache identities so Safari
    # cannot reuse prior custom bytes.
    loader_pat = r'(<script\b[^>]*\bsrc=["\'])/static/loader\.js(?:\?[^"\']*)?(["\'][^>]*>\s*</script>)'
    css_pat = r'(<link\b[^>]*\bhref=["\'])/static/custom\.css(?:\?[^"\']*)?(["\'][^>]*>)'

    if not re.search(loader_pat, index_text, flags=re.I):
        raise RuntimeError('stock loader.js script tag missing')
    if not re.search(css_pat, index_text, flags=re.I):
        raise RuntimeError('stock custom.css link tag missing')

    index_text = re.sub(
        loader_pat,
        rf'\1/static/loader.js?v={CACHE_GEN}\2',
        index_text,
        count=1,
        flags=re.I,
    )
    index_text = re.sub(
        css_pat,
        rf'\1/static/custom.css?v={CACHE_GEN}\2',
        index_text,
        count=1,
        flags=re.I,
    )

    # Receipt marker only; no executable bootstrap.
    if '</head>' not in index_text:
        raise RuntimeError('</head> anchor missing')
    index_text = index_text.replace(
        '</head>',
        f'\n\t\t<!-- {MARKER} -->\n\t</head>',
        1,
    )

    atomic_write_text(INDEX, index_text)

    # 5) Fail-closed verification.
    written = INDEX.read_text()
    checks = {
        'loader_frontend_empty': (FRONT_STATIC / 'loader.js').read_bytes() == b'',
        'loader_served_empty': (SERVED_STATIC / 'loader.js').read_bytes() == b'',
        'css_frontend_empty': (FRONT_STATIC / 'custom.css').read_bytes() == b'',
        'css_served_empty': (SERVED_STATIC / 'custom.css').read_bytes() == b'',
        'stock_app_exists': stock_app_path.is_file(),
        'stock_node_exists': stock_node_path.is_file(),
        'stock_app_reference': f'/_app/immutable/entry/{stock_app_name}' in written,
        'fresh_loader_generation': f'/static/loader.js?v={CACHE_GEN}' in written,
        'fresh_css_generation': f'/static/custom.css?v={CACHE_GEN}' in written,
        'receipt_marker': MARKER in written,
    }

    for name in KNOWN_CUSTOM_STATIC:
        if re.search(rf'/static/{re.escape(name)}(?:\?[^"\']*)?', written):
            checks['no_direct_ref_' + name] = False

    # No known executable custom inline IDs may remain.
    inline_ids = re.findall(r'<script\b[^>]*\bid=["\']([^"\']+)["\']', written, flags=re.I)
    if any(i.startswith(INLINE_ID_PREFIXES) for i in inline_ids):
        checks['no_custom_inline_bootstrap_ids'] = False

    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise RuntimeError('verification failed: ' + ','.join(failed))

except Exception:
    restore_backup()
    raise

receipt = {
    'status': 'STAGED_ON_DISK_PASS',
    'backup': str(BACKUP),
    'cache_generation': CACHE_GEN,
    'active_app_before': active_app,
    'stock_app': stock_app_name,
    'stock_node': stock_node_name,
    'loader_sha256': sha256_bytes((FRONT_STATIC / 'loader.js').read_bytes()),
    'custom_css_sha256': sha256_bytes((FRONT_STATIC / 'custom.css').read_bytes()),
    'custom_assets_deleted': False,
    'native_auth_changed': False,
    'backend_services_changed': False,
}
(BACKUP / 'STOCK_BOOTSTRAP_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')

print('STOCK_BOOTSTRAP=STAGED_ON_DISK_PASS')
print('OWNERSHIP=OPENWEBUI_BOOTSTRAP_ONLY')
print('CUSTOM_ASSETS_DELETED=NO')
print('NATIVE_AUTH_CHANGED=NO')
print('BACKEND_SERVICES_CHANGED=NO')
print('BACKUP=' + str(BACKUP))
print('ACTIVE_APP_BEFORE=' + active_app)
print('STOCK_APP=' + stock_app_name)
print('STOCK_NODE=' + stock_node_name)
print('CACHE_GENERATION=' + CACHE_GEN)
print('LOADER_BYTES=' + str((FRONT_STATIC / 'loader.js').stat().st_size))
print('CUSTOM_CSS_BYTES=' + str((FRONT_STATIC / 'custom.css').stat().st_size))
