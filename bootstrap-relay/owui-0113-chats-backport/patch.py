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

TAG = 'chatstartupfix20260929_1'
MARKER = 'owui-chats-startup-backport-v20260929.1'
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def atomic_write(path: Path, data: str):
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass

def stock_name(name: str) -> str:
    # Collapse only our known generated immutable suffixes back to the installed
    # OpenWebUI 0.11.3 hashed asset name when the original still exists.
    name = re.sub(r'\.pwa20260929_6(?=\.js$)', '', name)
    name = re.sub(r'\.chatstartupfix20260929_[A-Za-z0-9_-]+(?=\.js$)', '', name)
    return name

if not INDEX.is_file():
    raise SystemExit(f'ERROR index missing: {INDEX}')

index_text = INDEX.read_text()

# Idempotent verification.
if MARKER in index_text:
    app_m = re.search(r'/_app/immutable/entry/(app\.[^"\']+\.chatstartupfix20260929_1\.js)', index_text)
    if not app_m:
        raise SystemExit('ERROR marker present but fixed app entry is not referenced')
    app_path = ENTRY_DIR / app_m.group(1)
    if not app_path.is_file():
        raise SystemExit('ERROR fixed app entry is missing')
    app_text = app_path.read_text()
    node_m = re.search(r'\.\./nodes/(2\.[^"\']+\.chatstartupfix20260929_1\.js)', app_text)
    if not node_m:
        raise SystemExit('ERROR fixed app entry does not reference fixed node 2')
    node_path = NODE_DIR / node_m.group(1)
    if not node_path.is_file():
        raise SystemExit('ERROR fixed node 2 is missing')
    node_text = node_path.read_text()
    if re.search(r'await\s+Promise\.all\(\[\s*checkLocalDBChats\(\)\s*,', node_text, re.S):
        raise SystemExit('ERROR fixed node still blocks startup on checkLocalDBChats()')
    if not re.search(r'openDB\(["\']Chats["\']\s*,\s*1\)', node_text):
        raise SystemExit('ERROR fixed node no longer proves 0.11.3 legacy Chats lineage')
    print('ALREADY_APPLIED')
    print('MARKER=' + MARKER)
    print('APP=/_app/immutable/entry/' + app_m.group(1))
    print('NODE=/_app/immutable/nodes/' + node_m.group(1))
    raise SystemExit(0)

# Resolve the app entry currently referenced by the live document, then prefer the
# untouched original OpenWebUI immutable asset if the current reference is one of our
# previous experimental clones.
active_app_m = re.search(r'/_app/immutable/entry/(app\.[^"\']+\.js)', index_text)
if not active_app_m:
    raise SystemExit('ERROR active app entry reference not found')
active_app_name = active_app_m.group(1)
stock_app_name = stock_name(active_app_name)
stock_app_path = ENTRY_DIR / stock_app_name
active_app_path = ENTRY_DIR / active_app_name
source_app_path = stock_app_path if stock_app_path.is_file() else active_app_path
if not source_app_path.is_file():
    raise SystemExit('ERROR source app entry missing: ' + str(source_app_path))
source_app_name = source_app_path.name
source_app_text = source_app_path.read_text()

node_m = re.search(r'\.\./nodes/(2\.[^"\']+\.js)', source_app_text)
if not node_m:
    raise SystemExit('ERROR node 2 reference not found in source app entry')
active_node_name = node_m.group(1)
stock_node_name = stock_name(active_node_name)
stock_node_path = NODE_DIR / stock_node_name
active_node_path = NODE_DIR / active_node_name
source_node_path = stock_node_path if stock_node_path.is_file() else active_node_path
if not source_node_path.is_file():
    raise SystemExit('ERROR source node 2 missing: ' + str(source_node_path))
source_node_name = source_node_path.name
source_node_text = source_node_path.read_text()

# Prove this is the exact OpenWebUI 0.11.3 legacy-Chats lineage before mutating.
if not re.search(r'openDB\(["\']Chats["\']\s*,\s*1\)', source_node_text):
    raise SystemExit('ERROR OpenWebUI 0.11.3 legacy Chats openDB anchor missing')
if 'checkLocalDBChats' not in source_node_text:
    raise SystemExit('ERROR checkLocalDBChats symbol missing')

# Match the upstream semantic change exactly at the causal boundary:
# remove checkLocalDBChats() from the blocking startup Promise.all.
startup = re.compile(
    r'(clearChatInputStorage\(\);\s*try\s*\{\s*await\s+Promise\.all\(\[\s*)'
    r'checkLocalDBChats\(\)\s*,\s*',
    re.S,
)
matches = list(startup.finditer(source_node_text))
if len(matches) != 1:
    raise SystemExit('ERROR expected exactly one blocking checkLocalDBChats() startup call; found ' + str(len(matches)))

patched_node_text = startup.sub(r'\1', source_node_text, count=1)

# Strong postcondition: the legacy function/data remains untouched, but it is no longer
# on the app startup critical path. No timeout, IndexedDB monkeypatch, cache deletion,
# auth shim, LCARS change, voice change, or standalone predicate is introduced.
if re.search(r'await\s+Promise\.all\(\[\s*checkLocalDBChats\(\)\s*,', patched_node_text, re.S):
    raise SystemExit('ERROR blocking legacy Chats startup call remained')
if not re.search(r'openDB\(["\']Chats["\']\s*,\s*1\)', patched_node_text):
    raise SystemExit('ERROR legacy Chats implementation was unexpectedly altered')

new_node_name = source_node_name[:-3] + f'.{TAG}.js'
new_node_path = NODE_DIR / new_node_name
atomic_write(new_node_path, patched_node_text)

old_node_rel = '../nodes/' + source_node_name
new_node_rel = '../nodes/' + new_node_name
if old_node_rel not in source_app_text:
    raise SystemExit('ERROR source app does not contain expected source node reference')
patched_app_text = source_app_text.replace(old_node_rel, new_node_rel, 1)

new_app_name = source_app_name[:-3] + f'.{TAG}.js'
new_app_path = ENTRY_DIR / new_app_name
atomic_write(new_app_path, patched_app_text)

# Remove only superseded experimental startup scripts from the document. Leave all
# unrelated current UI, auth, gateway, voice, LCARS and runtime references untouched.
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

# Replace the currently active app entry with the new upstream-equivalent backport.
current_app_url = '/_app/immutable/entry/' + active_app_name
new_app_url = '/_app/immutable/entry/' + new_app_name
if current_app_url not in index_text:
    raise SystemExit('ERROR active app URL disappeared before index replacement')
index_text = index_text.replace(current_app_url, new_app_url, 1)

# If the document directly preloads node 2, move that preload to the fixed node too.
for old in {
    '/_app/immutable/nodes/' + active_node_name,
    '/_app/immutable/nodes/' + source_node_name,
}:
    index_text = index_text.replace(old, '/_app/immutable/nodes/' + new_node_name)

# A non-executable marker records the backport without introducing another bootstrap layer.
index_text = re.sub(r'\s*<!-- owui-chats-startup-backport-v[^>]*-->', '', index_text)
if '</head>' not in index_text:
    raise SystemExit('ERROR </head> insertion anchor missing')
index_text = index_text.replace('</head>', f'\n\t\t<!-- {MARKER} -->\n\t</head>', 1)

backup = INDEX.with_name(INDEX.name + f'.pre-{TAG}-{STAMP}')
shutil.copy2(INDEX, backup)
atomic_write(INDEX, index_text)

# Optional syntax qualification with the already-owned Node runtime.
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
        proc = subprocess.run([str(node_bin), '--check', str(tmp_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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

written = INDEX.read_text()
checks = {
    'marker': MARKER in written,
    'new_app_reference': new_app_url in written,
    'new_app_exists': new_app_path.is_file(),
    'new_node_reference': new_node_rel in new_app_path.read_text(),
    'new_node_exists': new_node_path.is_file(),
    'startup_call_removed': not bool(re.search(r'await\s+Promise\.all\(\[\s*checkLocalDBChats\(\)\s*,', new_node_path.read_text(), re.S)),
    'legacy_db_preserved': bool(re.search(r'openDB\(["\']Chats["\']\s*,\s*1\)', new_node_path.read_text())),
    'no_v5_inline_shim': 'owui-pwa-legacy-chats-bypass-v20260929.5' not in written,
    'no_v6_inline_guard': 'owui-pwa-startup-guard-v20260929.6' not in written,
}
failed = [k for k,v in checks.items() if not v]
if failed:
    shutil.copy2(backup, INDEX)
    raise SystemExit('ERROR verification failed; index restored: ' + ','.join(failed))

print('CHAT_STARTUP_BACKPORT=STAGED_ON_DISK_PASS')
print('SEMANTICS=UPSTREAM_EQUIVALENT_REMOVE_BLOCKING_STARTUP_CALL')
print('SCOPE=ALL_BROWSER_MODES')
print('DATA_DELETION=NONE')
print('INDEX_BACKUP=' + str(backup))
print('SOURCE_APP=' + source_app_name)
print('SOURCE_NODE=' + source_node_name)
print('APP=' + new_app_url)
print('NODE=/_app/immutable/nodes/' + new_node_name)
print('JS_SYNTAX=' + syntax)
print('INDEX_SHA256=' + sha256(INDEX))
print('APP_SHA256=' + sha256(new_app_path))
print('NODE_SHA256=' + sha256(new_node_path))
