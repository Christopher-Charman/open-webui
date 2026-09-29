#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import os
import re
import shutil
import subprocess
import tempfile

BASE = Path('/home/storage/781/4477781/user/webapp')
FRONTEND = BASE / 'envs/openwebui/lib/python3.11/site-packages/open_webui/frontend'
INDEX = FRONTEND / 'index.html'
ENTRY_DIR = FRONTEND / '_app/immutable/entry'
NODE_DIR = FRONTEND / '_app/immutable/nodes'

TAG = 'chatstartupfix20260929_2'
MARKER = 'owui-chats-startup-backport-v20260929.2'
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def atomic_write(path: Path, text: str):
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass

def is_stock_name(path: Path, prefix: str) -> bool:
    return bool(re.fullmatch(rf'{re.escape(prefix)}\.[A-Za-z0-9_-]+\.js', path.name))

if not INDEX.is_file():
    raise SystemExit(f'ERROR index missing: {INDEX}')
if not ENTRY_DIR.is_dir() or not NODE_DIR.is_dir():
    raise SystemExit('ERROR immutable entry/node directories missing')

index_text = INDEX.read_text()

# Idempotent success verification.
if MARKER in index_text:
    app_m = re.search(r'/_app/immutable/entry/(app\.[^"\']+\.chatstartupfix20260929_2\.js)', index_text)
    if not app_m:
        raise SystemExit('ERROR v2 marker present but fixed app entry reference missing')
    app_path = ENTRY_DIR / app_m.group(1)
    if not app_path.is_file():
        raise SystemExit('ERROR v2 fixed app entry missing')
    app_text = app_path.read_text()
    node_m = re.search(r'\.\./nodes/(2\.[^"\']+\.chatstartupfix20260929_2\.js)', app_text)
    if not node_m:
        raise SystemExit('ERROR v2 fixed app does not reference fixed node')
    node_path = NODE_DIR / node_m.group(1)
    if not node_path.is_file():
        raise SystemExit('ERROR v2 fixed node missing')
    node_text = node_path.read_text()
    if re.search(r'await\s+Promise\.all\(\[\s*checkLocalDBChats\(\)\s*,', node_text, re.S):
        raise SystemExit('ERROR v2 fixed node still blocks startup on Chats migration')
    print('ALREADY_APPLIED')
    print('MARKER=' + MARKER)
    print('APP=/_app/immutable/entry/' + app_m.group(1))
    print('NODE=/_app/immutable/nodes/' + node_m.group(1))
    raise SystemExit(0)

# Discover the actual installed stock OpenWebUI 0.11.3 node by semantic identity,
# rather than trusting an index restored from an older checkpoint.
node_candidates = []
for path in sorted(NODE_DIR.glob('2.*.js')):
    if not path.is_file() or not is_stock_name(path, '2'):
        continue
    try:
        text = path.read_text()
    except Exception:
        continue
    if 'checkLocalDBChats' not in text:
        continue
    if not re.search(r'openDB\(["\']Chats["\']\s*,\s*1\)', text):
        continue
    if not re.search(r'await\s+Promise\.all\(\[\s*checkLocalDBChats\(\)\s*,', text, re.S):
        continue
    node_candidates.append((path, text))

if len(node_candidates) != 1:
    print('DISCOVERY_NODE_CANDIDATES=' + str(len(node_candidates)))
    for p, _ in node_candidates:
        print('NODE_CANDIDATE=' + str(p))
    raise SystemExit('ERROR expected exactly one stock OpenWebUI 0.11.3 blocking Chats node')

source_node_path, source_node_text = node_candidates[0]
source_node_name = source_node_path.name

# Discover the coherent stock app entry that actually imports that node.
app_candidates = []
needle = '../nodes/' + source_node_name
for path in sorted(ENTRY_DIR.glob('app.*.js')):
    if not path.is_file() or not is_stock_name(path, 'app'):
        continue
    try:
        text = path.read_text()
    except Exception:
        continue
    if needle in text:
        app_candidates.append((path, text))

if len(app_candidates) != 1:
    print('DISCOVERY_APP_CANDIDATES=' + str(len(app_candidates)))
    for p, _ in app_candidates:
        print('APP_CANDIDATE=' + str(p))
    raise SystemExit('ERROR expected exactly one coherent stock app entry for discovered node')

source_app_path, source_app_text = app_candidates[0]
source_app_name = source_app_path.name

# Record the stale document reference, if any, as evidence only.
active_app_m = re.search(r'/_app/immutable/entry/(app\.[^"\']+\.js)', index_text)
active_app_name = active_app_m.group(1) if active_app_m else ''
active_app_exists = bool(active_app_name and (ENTRY_DIR / active_app_name).is_file())

# Apply only the upstream semantic delta:
# remove checkLocalDBChats() from the blocking startup Promise.all.
startup = re.compile(
    r'(clearChatInputStorage\(\);\s*try\s*\{\s*await\s+Promise\.all\(\[\s*)'
    r'checkLocalDBChats\(\)\s*,\s*',
    re.S,
)
matches = list(startup.finditer(source_node_text))
if len(matches) != 1:
    raise SystemExit('ERROR blocking startup call count drifted: ' + str(len(matches)))

patched_node_text = startup.sub(r'\1', source_node_text, count=1)

# Postconditions: preserve the legacy function/database bytes, remove only startup blocking.
if re.search(r'await\s+Promise\.all\(\[\s*checkLocalDBChats\(\)\s*,', patched_node_text, re.S):
    raise SystemExit('ERROR blocking Chats startup call remained')
if 'checkLocalDBChats' not in patched_node_text:
    raise SystemExit('ERROR legacy migration function was unexpectedly removed')
if not re.search(r'openDB\(["\']Chats["\']\s*,\s*1\)', patched_node_text):
    raise SystemExit('ERROR legacy Chats database implementation was unexpectedly altered')

new_node_name = source_node_name[:-3] + f'.{TAG}.js'
new_node_path = NODE_DIR / new_node_name
atomic_write(new_node_path, patched_node_text)

new_node_rel = '../nodes/' + new_node_name
patched_app_text = source_app_text.replace(needle, new_node_rel, 1)
if new_node_rel not in patched_app_text:
    raise SystemExit('ERROR failed to repoint app entry to fixed node')

new_app_name = source_app_name[:-3] + f'.{TAG}.js'
new_app_path = ENTRY_DIR / new_app_name
atomic_write(new_app_path, patched_app_text)

# Remove only superseded startup experiments. Do not alter LCARS, voice, auth, gateway,
# settings, model warming, TTS, terminal, or other current layers.
for script_id in (
    'owui-pwa-legacy-chats-bypass-v20260929.5',
    'owui-pwa-startup-guard-v20260929.6',
):
    index_text = re.sub(
        rf'\s*<script id="{re.escape(script_id)}">.*?</script>',
        '',
        index_text,
        count=1,
        flags=re.S,
    )

new_app_url = '/_app/immutable/entry/' + new_app_name

# Repair document/bundle coherence regardless of whether the currently referenced app exists.
if active_app_m:
    index_text = (
        index_text[:active_app_m.start()]
        + new_app_url
        + index_text[active_app_m.end():]
    )
else:
    raise SystemExit('ERROR no app entry URL found in index.html')

# Repoint any direct stock/stale node preload/reference to the fixed node where present.
for node_ref in re.findall(r'/_app/immutable/nodes/(2\.[^"\']+\.js)', index_text):
    if node_ref == source_node_name or not (NODE_DIR / node_ref).is_file():
        index_text = index_text.replace(
            '/_app/immutable/nodes/' + node_ref,
            '/_app/immutable/nodes/' + new_node_name
        )

# Non-executable receipt marker only.
index_text = re.sub(r'\s*<!-- owui-chats-startup-backport-v[^>]*-->', '', index_text)
if '</head>' not in index_text:
    raise SystemExit('ERROR </head> anchor missing')
index_text = index_text.replace('</head>', f'\n\t\t<!-- {MARKER} -->\n\t</head>', 1)

backup = INDEX.with_name(INDEX.name + f'.pre-{TAG}-{STAMP}')
shutil.copy2(INDEX, backup)
atomic_write(INDEX, index_text)

# Syntax qualification using the owned local Node build when available.
node_bins = [
    BASE / '.local/node22-glibc217/bin/node',
    BASE / '.local/node22-el7/bin/node',
]
node_bin = next((p for p in node_bins if p.is_file() and os.access(p, os.X_OK)), None)
syntax = 'SKIP_NODE_NOT_FOUND'
if node_bin:
    fd, tmp = tempfile.mkstemp(prefix='owui-node2-check-', suffix='.mjs', dir=str(BASE))
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        tmp_path.write_text(patched_node_text)
        proc = subprocess.run([str(node_bin), '--check', str(tmp_path)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            shutil.copy2(backup, INDEX)
            try: new_app_path.unlink()
            except FileNotFoundError: pass
            try: new_node_path.unlink()
            except FileNotFoundError: pass
            print(proc.stderr[-3000:])
            raise SystemExit('ERROR patched node failed JavaScript syntax qualification; index restored')
        syntax = 'PASS'
    finally:
        try: tmp_path.unlink()
        except FileNotFoundError: pass

# Final coherence verification.
written = INDEX.read_text()
checks = {
    'marker': MARKER in written,
    'document_references_fixed_app': new_app_url in written,
    'fixed_app_exists': new_app_path.is_file(),
    'fixed_app_references_fixed_node': new_node_rel in new_app_path.read_text(),
    'fixed_node_exists': new_node_path.is_file(),
    'blocking_call_removed': not bool(re.search(
        r'await\s+Promise\.all\(\[\s*checkLocalDBChats\(\)\s*,',
        new_node_path.read_text(), re.S
    )),
    'legacy_db_preserved': bool(re.search(
        r'openDB\(["\']Chats["\']\s*,\s*1\)',
        new_node_path.read_text()
    )),
    'no_v5_shim': 'owui-pwa-legacy-chats-bypass-v20260929.5' not in written,
    'no_v6_guard': 'owui-pwa-startup-guard-v20260929.6' not in written,
}
failed = [k for k,v in checks.items() if not v]
if failed:
    shutil.copy2(backup, INDEX)
    raise SystemExit('ERROR final verification failed; index restored: ' + ','.join(failed))

print('CHAT_STARTUP_BACKPORT_V2=STAGED_ON_DISK_PASS')
print('COHERENCE_REPAIR=PASS')
print('SEMANTICS=UPSTREAM_EQUIVALENT_REMOVE_BLOCKING_STARTUP_CALL')
print('SCOPE=ALL_BROWSER_MODES')
print('DATA_DELETION=NONE')
print('INDEX_BACKUP=' + str(backup))
print('STALE_INDEX_APP=' + (active_app_name or 'NONE'))
print('STALE_INDEX_APP_EXISTS=' + ('YES' if active_app_exists else 'NO'))
print('DISCOVERED_STOCK_APP=' + source_app_name)
print('DISCOVERED_STOCK_NODE=' + source_node_name)
print('APP=' + new_app_url)
print('NODE=/_app/immutable/nodes/' + new_node_name)
print('JS_SYNTAX=' + syntax)
print('INDEX_SHA256=' + sha256(INDEX))
print('APP_SHA256=' + sha256(new_app_path))
print('NODE_SHA256=' + sha256(new_node_path))
