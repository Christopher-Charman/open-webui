#!/home/storage/781/4477781/user/webapp/envs/open-terminal/bin/python
from __future__ import print_function

import hashlib
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path('/home/storage/781/4477781/user')
BASE = HOME / 'webapp'
CONTROLLER = BASE / 'passenger_wsgi.py'
MODULE = BASE / 'chatgpt_bootstrap_control.py'
KEYDIR = HOME / '.key'
TOKENFILE = KEYDIR / 'chatgpt-bootstrap.token'
EXPIREFILE = KEYDIR / 'chatgpt-bootstrap.expires'
BACKUP = BASE / 'passenger_wsgi.py.pre-chatgpt-bootstrap-control-v1'
PYC = BASE / 'passenger_wsgi.pyc'
EXPECTED_USER = 'csh3280350'
EXPECTED_UID = 2257347
TTL_SECONDS = 7200
MARKER = 'CHATGPT_BOOTSTRAP_CONTROL_V1'

MODULE_TEXT = r'''# CHATGPT_BOOTSTRAP_CONTROL_V1
from __future__ import print_function
import base64
import hmac
import json
import os
import pwd
import subprocess
import time

HOME = "/home/storage/781/4477781/user"
BASE = HOME + "/webapp"
TOKENFILE = HOME + "/.key/chatgpt-bootstrap.token"
EXPIREFILE = HOME + "/.key/chatgpt-bootstrap.expires"
PREFIX = "/__chatgpt_bootstrap/"
MAX_BODY = 32768
MAX_OUTPUT = 262144
MAX_COMMAND = 8192
MAX_TIMEOUT = 90

def _read(path, limit=8192):
    try:
        with open(path, "rb") as f:
            return f.read(limit).strip()
    except Exception:
        return b""

def _eq(a, b):
    try:
        return hmac.compare_digest(a, b)
    except Exception:
        if len(a) != len(b):
            return False
        v = 0
        for x, y in zip(bytearray(a), bytearray(b)):
            v |= x ^ y
        return v == 0

def _json(start_response, status, obj):
    body = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    start_response(status, [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("Pragma", "no-cache"),
        ("X-Content-Type-Options", "nosniff"),
        ("X-ChatGPT-Bootstrap-Control", "v1"),
    ])
    return [body]

def _authorized(environ):
    raw = environ.get("HTTP_AUTHORIZATION", "")
    if not raw.startswith("Bearer "):
        return False
    supplied = raw[7:].strip()
    expected = _read(TOKENFILE)
    if not expected or not supplied:
        return False
    try:
        expires = int(_read(EXPIREFILE) or b"0")
    except Exception:
        return False
    if expires <= int(time.time()):
        return False
    return _eq(supplied.encode("ascii", "ignore"), expected)

def _safe_cwd(raw):
    if not raw:
        return BASE
    try:
        path = os.path.realpath(raw)
    except Exception:
        return None
    if path == HOME or path.startswith(HOME + os.sep):
        return path
    return None

def _read_json(environ):
    try:
        n = int(environ.get("CONTENT_LENGTH") or "0")
    except Exception:
        n = 0
    if n < 0 or n > MAX_BODY:
        raise ValueError("request_too_large")
    raw = environ["wsgi.input"].read(n) if n else b"{}"
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("invalid_json")
    if not isinstance(obj, dict):
        raise ValueError("invalid_json")
    return obj

def _exec(command, cwd, timeout):
    env = {
        "HOME": HOME,
        "USER": "csh3280350",
        "LOGNAME": "csh3280350",
        "PATH": BASE + "/envs/open-terminal/bin:" + BASE + "/miniconda/bin:/usr/local/bin:/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
    }
    devnull = open("/dev/null", "rb")
    try:
        p = subprocess.Popen(
            ["/bin/bash", "-lc", command],
            cwd=cwd,
            env=env,
            stdin=devnull,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
        deadline = time.time() + timeout
        timed_out = False
        while p.poll() is None and time.time() < deadline:
            time.sleep(0.10)
        if p.poll() is None:
            timed_out = True
            try: p.terminate()
            except Exception: pass
            time.sleep(0.5)
        if p.poll() is None:
            try: p.kill()
            except Exception: pass
        try: out = p.stdout.read(MAX_OUTPUT + 1)
        except Exception: out = b""
        truncated = len(out) > MAX_OUTPUT
        if truncated: out = out[:MAX_OUTPUT]
        return p.returncode, timed_out, truncated, out
    finally:
        try: devnull.close()
        except Exception: pass

def handle(environ, start_response):
    if not _authorized(environ):
        return _json(start_response, "401 Unauthorized", {"ok": False, "error": "unauthorized"})
    path = environ.get("PATH_INFO", "")
    method = environ.get("REQUEST_METHOD", "GET").upper()
    if path == PREFIX + "health" and method == "GET":
        try: expires = int(_read(EXPIREFILE) or b"0")
        except Exception: expires = 0
        return _json(start_response, "200 OK", {
            "ok": True,
            "service": "chatgpt-bootstrap-control-v1",
            "user": pwd.getpwuid(os.getuid()).pw_name,
            "uid": os.getuid(),
            "cwd": os.getcwd(),
            "namespace": HOME,
            "expires_unix": expires,
            "ttl_seconds": max(0, expires - int(time.time())),
        })
    if path == PREFIX + "exec" and method == "POST":
        try: obj = _read_json(environ)
        except ValueError as e:
            return _json(start_response, "400 Bad Request", {"ok": False, "error": str(e)})
        command = obj.get("command", "")
        if not isinstance(command, basestring) or not command or len(command) > MAX_COMMAND:
            return _json(start_response, "400 Bad Request", {"ok": False, "error": "invalid_command"})
        cwd = _safe_cwd(obj.get("cwd"))
        if not cwd or not os.path.isdir(cwd):
            return _json(start_response, "400 Bad Request", {"ok": False, "error": "invalid_cwd"})
        try: timeout = int(obj.get("timeout", 30))
        except Exception: timeout = 30
        timeout = max(1, min(MAX_TIMEOUT, timeout))
        rc, timed_out, truncated, out = _exec(command, cwd, timeout)
        return _json(start_response, "200 OK", {
            "ok": True,
            "rc": rc,
            "timed_out": timed_out,
            "truncated": truncated,
            "output_b64": base64.b64encode(out).decode("ascii"),
        })
    return _json(start_response, "404 Not Found", {"ok": False, "error": "not_found"})
'''

IMPORT_LINE = 'import chatgpt_bootstrap_control as _chatgpt_bootstrap_control\n'
ROUTE_BLOCK = '''
    # CHATGPT_BOOTSTRAP_CONTROL_V1: temporary machine bootstrap route.
    if path.startswith("/__chatgpt_bootstrap/"):
        return _chatgpt_bootstrap_control.handle(environ, start_response)
'''

def sha256(path):
    h = hashlib.sha256()
    with open(str(path), 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def atomic_write(path, data, mode):
    path = Path(path)
    fd, tmpname = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmpname, mode)
        os.replace(tmpname, str(path))
    finally:
        try: os.unlink(tmpname)
        except OSError: pass

def fail(msg):
    print('ERROR=' + msg)
    raise SystemExit(1)

def main():
    print('CHATGPT_BOOTSTRAP_CONTROL_INSTALL_V1')
    user = pwd.getpwuid(os.getuid()).pw_name
    print('user=' + user)
    print('uid=' + str(os.getuid()))
    if user != EXPECTED_USER or os.getuid() != EXPECTED_UID:
        fail('unexpected execution identity')
    token = os.environ.get('CHATGPT_SHARE_TOKEN', '').strip()
    if not re.match(r'^[A-Za-z0-9_-]{48,128}$', token):
        fail('CHATGPT_SHARE_TOKEN missing or invalid')
    if not CONTROLLER.is_file():
        fail('Passenger controller missing')
    KEYDIR.mkdir(parents=True, exist_ok=True)
    os.chmod(str(KEYDIR), 0o700)
    expires = int(time.time()) + TTL_SECONDS
    atomic_write(TOKENFILE, (token + '\n').encode('ascii'), 0o600)
    atomic_write(EXPIREFILE, (str(expires) + '\n').encode('ascii'), 0o600)
    atomic_write(MODULE, MODULE_TEXT.encode('utf-8'), 0o600)
    subprocess.check_call(['/usr/bin/python', '-m', 'py_compile', str(MODULE)])
    source = CONTROLLER.read_text(encoding='utf-8')
    before_sha = sha256(CONTROLLER)
    changed = False
    if MARKER not in source:
        if 'import urllib\n' in source:
            source = source.replace('import urllib\n', 'import urllib\n' + IMPORT_LINE, 1)
        elif 'import time\n' in source:
            source = source.replace('import time\n', 'import time\n' + IMPORT_LINE, 1)
        else:
            fail('safe import insertion point not found')
        anchor = '    path = environ.get("PATH_INFO", "/")\n\n'
        if anchor not in source:
            fail('application path anchor not found')
        source = source.replace(anchor, anchor + ROUTE_BLOCK + '\n', 1)
        changed = True
    if changed:
        if not BACKUP.exists():
            shutil.copy2(str(CONTROLLER), str(BACKUP))
            os.chmod(str(BACKUP), 0o600)
        atomic_write(CONTROLLER, source.encode('utf-8'), 0o704)
        subprocess.check_call(['/usr/bin/python', '-m', 'py_compile', str(CONTROLLER)])
        try:
            if PYC.exists(): PYC.unlink()
        except Exception:
            pass
    restart_dir = BASE / 'tmp'
    restart_dir.mkdir(parents=True, exist_ok=True)
    (restart_dir / 'restart.txt').touch()
    print('controller_before_sha256=' + before_sha)
    print('controller_after_sha256=' + sha256(CONTROLLER))
    print('controller_action=' + ('PATCHED' if changed else 'ALREADY_PRESENT'))
    print('module_sha256=' + sha256(MODULE))
    print('token_file=' + str(TOKENFILE))
    print('token_disclosed=NO')
    print('expires_unix=' + str(expires))
    print('public_health=https://powerpc-darwin.org/__chatgpt_bootstrap/health')
    print('public_exec=https://powerpc-darwin.org/__chatgpt_bootstrap/exec')
    print('CHATGPT_BOOTSTRAP_CONTROL=INSTALLED')

if __name__ == '__main__':
    main()
