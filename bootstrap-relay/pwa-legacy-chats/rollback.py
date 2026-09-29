#!/usr/bin/env python3
from pathlib import Path
import glob, shutil
TARGET = Path('/home/storage/781/4477781/user/webapp/envs/openwebui/lib/python3.11/site-packages/open_webui/frontend/index.html')
backups = sorted(glob.glob(str(TARGET.with_name('index.html.pre-pwa-idb-bypass-*'))))
if not backups:
    raise SystemExit('ERROR no rollback backup found')
src = Path(backups[-1])
shutil.copy2(src, TARGET)
print('ROLLBACK=STAGED_ON_DISK')
print('RESTORED=' + str(src))
