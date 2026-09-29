#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import re
import shutil

BASE = Path('/home/storage/781/4477781/user/webapp')
FRONTEND = BASE / 'envs/openwebui/lib/python3.11/site-packages/open_webui/frontend'
INDEX = FRONTEND / 'index.html'
MARKER = 'owui-pwa-startup-guard-v20260929.6'
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
TAG = 'pwa20260929_6'

INLINE_BLOCK = r'''
		<script id="owui-pwa-startup-guard-v20260929.6">
			(() => {
				'use strict';
				if (window.__OWUI_PWA_STARTUP_GUARD__ === '20260929.6') return;
				const factory = window.indexedDB;
				const blocked = new Set(['Chats', 'owui-client-runtime']);
				let installed = false;
				if (factory && typeof factory.open === 'function') {
					const original = factory.open.bind(factory);
					const guarded = function(name, version) {
						if (blocked.has(String(name))) {
							throw new Error('OWUI startup IndexedDB bypass: ' + String(name));
						}
						return arguments.length > 1 ? original(name, version) : original(name);
					};
					try {
						Object.defineProperty(factory, 'open', {
							configurable: true,
							writable: true,
							value: guarded
						});
						installed = factory.open === guarded;
					} catch (_) {}
					if (!installed) {
						try {
							const proto = Object.getPrototypeOf(factory);
							const protoOpen = proto && proto.open;
							if (typeof protoOpen === 'function') {
								Object.defineProperty(proto, 'open', {
									configurable: true,
									writable: true,
									value: function(name) {
										if (blocked.has(String(name))) {
											throw new Error('OWUI startup IndexedDB bypass: ' + String(name));
										}
										return protoOpen.apply(this, arguments);
									}
								});
								installed = true;
							}
						} catch (_) {}
					}
				}
				window.__OWUI_PWA_STARTUP_GUARD__ = installed ? '20260929.6' : '20260929.6-no-idb-hook';
				document.documentElement.dataset.owuiPwaStartupGuard = window.__OWUI_PWA_STARTUP_GUARD__;
			})();
		</script>'''

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def backup(path: Path) -> Path:
    dst = path.with_name(path.name + f'.pre-{TAG}-{STAMP}')
    shutil.copy2(path, dst)
    return dst

if not INDEX.exists():
    raise SystemExit(f'ERROR index missing: {INDEX}')

index_text = INDEX.read_text()

# Discover the concrete SvelteKit app entry currently referenced by this installed build.
app_match = re.search(r'/_app/immutable/entry/(app\.[A-Za-z0-9_-]+\.js)', index_text)
if not app_match:
    raise SystemExit('ERROR app entry reference not found in index.html')
app_name = app_match.group(1)
app_path = FRONTEND / '_app/immutable/entry' / app_name
if not app_path.exists():
    raise SystemExit(f'ERROR app entry missing: {app_path}')
app_text = app_path.read_text()

# Discover the concrete app-layout node containing checkLocalDBChats.
node_match = re.search(r'\.\./nodes/(2\.[A-Za-z0-9_-]+\.js)', app_text)
if not node_match:
    raise SystemExit('ERROR node 2 reference not found in app entry')
node_name = node_match.group(1)
node_path = FRONTEND / '_app/immutable/nodes' / node_name
if not node_path.exists():
    raise SystemExit(f'ERROR node 2 missing: {node_path}')
node_text = node_path.read_text()

# Prove we are patching the exact 0.11.3 startup path observed in the live capture.
idb_anchor = 'set(DB, await openDB("Chats", 1));'
if idb_anchor not in node_text:
    raise SystemExit('ERROR legacy Chats startup anchor missing from node 2')

promise_prefix = '''    clearChatInputStorage();
    try {
      await Promise.all(['''
promise_suffix = '''      ]);
    } catch (e) {'''
start = node_text.find(promise_prefix)
if start < 0:
    raise SystemExit('ERROR startup Promise.all prefix missing from node 2')
inner_start = start + len(promise_prefix)
end = node_text.find(promise_suffix, inner_start)
if end < 0:
    raise SystemExit('ERROR startup Promise.all suffix missing from node 2')
inner = node_text[inner_start:end]

# Directly neutralize only the obsolete local-chat migration. Data is not deleted.
patched_node = node_text.replace(
    idb_anchor,
    'set(DB, null);\n      return;',
    1,
)

# Bound the full best-effort startup group. Any task may still finish later, but none can
# hold the whole app on the central spinner indefinitely.
old_group = promise_prefix + inner + promise_suffix
new_group = '''    clearChatInputStorage();
    try {
      await Promise.race([
        Promise.all([''' + inner + '''      ]).catch((e) => {
          console.error("OWUI startup guard: initialization error", e);
          return [];
        }),
        new Promise((resolve) => setTimeout(() => {
          console.warn("OWUI startup guard: initialization timeout; continuing");
          document.documentElement.dataset.owuiBootGuard = "timeout";
          resolve([]);
        }, 8000))
      ]);
    } catch (e) {'''
if old_group not in patched_node:
    raise SystemExit('ERROR startup Promise.all replacement target drifted')
patched_node = patched_node.replace(old_group, new_group, 1)

if idb_anchor in patched_node:
    raise SystemExit('ERROR legacy Chats anchor remained after patch')
if 'OWUI startup guard: initialization timeout; continuing' not in patched_node:
    raise SystemExit('ERROR startup timeout guard marker missing after patch')

new_node_name = node_name[:-3] + f'.{TAG}.js'
new_node_path = node_path.with_name(new_node_name)
new_node_path.write_text(patched_node)

# Create a new app-entry URL that points at the new node URL. This defeats the existing
# six-month immutable cache without editing the original hashed artefacts in place.
old_node_rel = f'../nodes/{node_name}'
new_node_rel = f'../nodes/{new_node_name}'
if old_node_rel not in app_text:
    raise SystemExit('ERROR node reference missing from app entry')
patched_app = app_text.replace(old_node_rel, new_node_rel)
new_app_name = app_name[:-3] + f'.{TAG}.js'
new_app_path = app_path.with_name(new_app_name)
new_app_path.write_text(patched_app)

# Replace prior experimental inline guard rather than stacking it.
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

charset = '<meta charset="utf-8" />'
if charset not in index_text:
    raise SystemExit('ERROR charset insertion anchor missing')
index_text = index_text.replace(charset, charset + INLINE_BLOCK, 1)

old_app_url = f'/_app/immutable/entry/{app_name}'
new_app_url = f'/_app/immutable/entry/{new_app_name}'
old_node_url = f'/_app/immutable/nodes/{node_name}'
new_node_url = f'/_app/immutable/nodes/{new_node_name}'
if old_app_url not in index_text:
    raise SystemExit('ERROR app entry URL missing from index before replacement')
index_text = index_text.replace(old_app_url, new_app_url)
index_text = index_text.replace(old_node_url, new_node_url)

# Bust the long-lived custom-client cache keys observed in the 2026-09-29 WebArchive.
index_text = index_text.replace('loader.js?v=20260929.4', 'loader.js?v=20260929.6')
index_text = index_text.replace('build=20260929.4', 'build=20260929.6')

index_backup = backup(INDEX)
INDEX.write_text(index_text)

# Final on-disk invariants.
written = INDEX.read_text()
checks = {
    'inline_marker': MARKER in written,
    'new_app_url': new_app_url in written,
    'new_node_url': new_node_url in written,
    'new_app_exists': new_app_path.exists(),
    'new_node_exists': new_node_path.exists(),
    'node_direct_bypass': 'set(DB, null);' in new_node_path.read_text(),
    'node_timeout_guard': 'OWUI startup guard: initialization timeout; continuing' in new_node_path.read_text(),
}
failed = [k for k, v in checks.items() if not v]
if failed:
    raise SystemExit('ERROR verification failed: ' + ','.join(failed))

print('PATCH=STAGED_ON_DISK')
print('MARKER=' + MARKER)
print('BACKUP=' + str(index_backup))
print('APP=' + new_app_url)
print('NODE=' + new_node_url)
print('INDEX_SHA256=' + sha256(INDEX))
print('APP_SHA256=' + sha256(new_app_path))
print('NODE_SHA256=' + sha256(new_node_path))
