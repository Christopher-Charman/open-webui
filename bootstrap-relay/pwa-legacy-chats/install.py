#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib, shutil

TARGET = Path('/home/storage/781/4477781/user/webapp/envs/openwebui/lib/python3.11/site-packages/open_webui/frontend/index.html')
MARKER = 'owui-pwa-legacy-chats-bypass-v20260929.5'
INSERT_AFTER = '<meta charset="utf-8" />'
BLOCK = r'''
		<script id="owui-pwa-legacy-chats-bypass-v20260929.5">
			(() => {
				'use strict';
				const standalone = window.matchMedia?.('(display-mode: standalone)')?.matches === true || navigator.standalone === true;
				if (!standalone || !window.IDBFactory || window.__OWUI_LEGACY_CHATS_BYPASS__) return;
				const proto = window.IDBFactory.prototype;
				const originalOpen = proto.open;
				proto.open = function(name) {
					if (String(name) === 'Chats') {
						throw new Error('Legacy Chats IndexedDB migration bypassed in standalone PWA');
					}
					return originalOpen.apply(this, arguments);
				};
				window.__OWUI_LEGACY_CHATS_BYPASS__ = '20260929.5';
			})();
		</script>'''

if not TARGET.exists():
    raise SystemExit(f'ERROR target missing: {TARGET}')
text = TARGET.read_text()
if MARKER in text:
    print('ALREADY_APPLIED')
    raise SystemExit(0)
if INSERT_AFTER not in text:
    raise SystemExit('ERROR insertion anchor missing')
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup = TARGET.with_name(f'index.html.pre-pwa-idb-bypass-{stamp}')
shutil.copy2(TARGET, backup)
patched = text.replace(INSERT_AFTER, INSERT_AFTER + BLOCK, 1)
TARGET.write_text(patched)
print('PATCH=STAGED_ON_DISK')
print('TARGET_SHA256=' + hashlib.sha256(TARGET.read_bytes()).hexdigest())
print('BACKUP=' + str(backup))
print('MARKER=' + MARKER)
