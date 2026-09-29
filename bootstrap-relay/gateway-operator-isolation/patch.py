#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib, os, shutil, subprocess, sys, tempfile

BASE = Path('/home/storage/781/4477781/user/webapp')
TARGET = BASE / 'passenger_wsgi.py'
PYC = BASE / 'passenger_wsgi.pyc'
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
BACKUP = BASE / ('passenger_wsgi.py.pre-operator-path-isolation-' + STAMP + '.bak')
MARKER = 'OPENWEBUI_GATEWAY_OPERATOR_PATH_ISOLATION_V1'

OLD = '''def application(environ, start_response):
    try:
        ensure_management_sshd()
    except Exception:
        pass

    try:
        ensure_ot_runtime()
    except Exception:
        pass

    path = environ.get("PATH_INFO", "/")

    if path == "/__owui_gate":
        return gate_bootstrap(environ, start_response)

    operator_path = (
        path == "/terminal"
        or path.startswith("/terminal/")
        or path.startswith("/__webapp_admin/")
        or path == "/__owui_control/status"
    )

    if operator_path and not gate_ok(environ):
'''

NEW = '''def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")

    if path == "/__owui_gate":
        return gate_bootstrap(environ, start_response)

    operator_path = (
        path == "/terminal"
        or path.startswith("/terminal/")
        or path.startswith("/__webapp_admin/")
        or path == "/__owui_control/status"
    )

    # OPENWEBUI_GATEWAY_OPERATOR_PATH_ISOLATION_V1
    # Operator-plane lifecycle work must never sit on the normal OpenWebUI
    # frontend/API/static/Socket.IO request path.
    if operator_path:
        try:
            ensure_management_sshd()
        except Exception:
            pass

    terminal_runtime_path = (
        path == "/terminal"
        or path.startswith("/terminal/")
        or path.startswith("/__webapp_admin/open-terminal")
    )
    if terminal_runtime_path:
        try:
            ensure_ot_runtime()
        except Exception:
            pass

    if operator_path and not gate_ok(environ):
'''

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

if not TARGET.is_file():
    raise SystemExit('ERROR target missing: %s' % TARGET)

original = TARGET.read_text()

if MARKER in original:
    print('GATEWAY_ISOLATION=ALREADY_STAGED')
    print('controller_sha256=' + sha256(TARGET))
    print('PASSENGER_RESTART_REQUIRED=YES')
    raise SystemExit(0)

if OLD not in original:
    # Fail closed and expose only structural diagnostics, never file contents.
    print('GATEWAY_ISOLATION=FAIL expected_application_preamble_not_found')
    print('has_ensure_management_sshd=' + str('ensure_management_sshd()' in original))
    print('has_ensure_ot_runtime=' + str('ensure_ot_runtime()' in original))
    print('has_operator_path=' + str('operator_path = (' in original))
    raise SystemExit(2)

if original.count(OLD) != 1:
    raise SystemExit('ERROR application preamble matched more than once')

candidate = original.replace(OLD, NEW, 1)

# Preserve the proven OpenWebUI runtime health guard and proxy identity.
for invariant in (
    'def proxy_request(environ, start_response):',
    'if not ensure_runtime():',
    'X-OpenWebUI-Proxy',
    'def gate_ok(environ):',
    'def gate_bootstrap(environ, start_response):',
    'return proxy_request(environ, start_response)',
):
    if invariant not in candidate:
        raise SystemExit('ERROR required gateway invariant missing: ' + invariant)

# Native OpenWebUI must remain the normal frontend auth boundary; the deployment
# gate stays scoped to operator_path exactly as before.
if 'if operator_path and not gate_ok(environ):' not in candidate:
    raise SystemExit('ERROR operator gate invariant missing')

# Compile with the Passenger interpreter before replacing live source.
fd, tmp = tempfile.mkstemp(prefix='passenger_wsgi.gateway-isolation.', suffix='.py', dir=str(BASE))
os.close(fd)
tmp_path = Path(tmp)
try:
    tmp_path.write_text(candidate)
    proc = subprocess.run(
        ['/usr/bin/python', '-m', 'py_compile', str(tmp_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if proc.returncode != 0:
        print('GATEWAY_ISOLATION=FAIL python2_compile')
        print(proc.stderr[-2000:])
        raise SystemExit(2)

    shutil.copy2(TARGET, BACKUP)
    os.chmod(BACKUP, 0o600)

    # Atomic same-filesystem replacement.
    fd2, tmp2 = tempfile.mkstemp(prefix='passenger_wsgi.new.', dir=str(BASE))
    try:
        with os.fdopen(fd2, 'w') as f:
            f.write(candidate)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp2, TARGET.stat().st_mode & 0o777)
        os.replace(tmp2, TARGET)
    finally:
        try: os.unlink(tmp2)
        except FileNotFoundError: pass

    try:
        PYC.unlink()
    except FileNotFoundError:
        pass

    # Readback and recompile live file.
    live = TARGET.read_text()
    if MARKER not in live or OLD in live:
        shutil.copy2(BACKUP, TARGET)
        raise SystemExit('ERROR live readback failed; backup restored')

    proc2 = subprocess.run(
        ['/usr/bin/python', '-m', 'py_compile', str(TARGET)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if proc2.returncode != 0:
        shutil.copy2(BACKUP, TARGET)
        print(proc2.stderr[-2000:])
        raise SystemExit('ERROR live python2 compile failed; backup restored')

finally:
    try: tmp_path.unlink()
    except FileNotFoundError: pass
    # Python 2 py_compile may leave tmp_path + c.
    try: Path(str(tmp_path) + 'c').unlink()
    except FileNotFoundError: pass

print('GATEWAY_ISOLATION=STAGED_ON_DISK_PASS')
print('backup=' + str(BACKUP))
print('controller_sha256=' + sha256(TARGET))
print('normal_openwebui_path=NO_MANAGEMENT_SSH_OR_OPEN_TERMINAL_ENSURES')
print('operator_gate=PRESERVED')
print('native_openwebui_auth=UNCHANGED')
print('openwebui_health_guard=PRESERVED')
print('PASSENGER_RESTART_REQUIRED=YES')
