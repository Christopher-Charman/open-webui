#!/usr/bin/env bash
set -euo pipefail
umask 077

ACCOUNT="/home/storage/781/4477781/user"
BASE="$ACCOUNT/webapp"
STATE="$BASE/.continuity-control"
WSGI="$BASE/passenger_wsgi.py"
AGENT_SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_SRC="$AGENT_SRC_DIR/agent.sh"
AGENT="$STATE/agent.sh"
LOG="$STATE/agent.log"
PIDFILE="$STATE/agent.pid"

[ "$(id -u)" = "2257347" ] || {
  echo "INSTALL=REFUSED uid=$(id -u) expected=2257347"
  exit 2
}
[ -d "$BASE" ] || { echo "INSTALL=FAIL missing_webapp"; exit 2; }
[ -f "$WSGI" ] || { echo "INSTALL=FAIL missing_passenger_wsgi"; exit 2; }
[ -f "$AGENT_SRC" ] || { echo "INSTALL=FAIL missing_agent_source"; exit 2; }

mkdir -p "$STATE"
chmod 700 "$STATE"
install -m 700 "$AGENT_SRC" "$AGENT"

if [ -f "$PIDFILE" ]; then
  old="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "$old" ] && kill -0 "$old" 2>/dev/null; then
    kill "$old" 2>/dev/null || true
    sleep 1
  fi
fi

nohup /usr/bin/setsid /bin/bash "$AGENT" >>"$LOG" 2>&1 </dev/null &
pid=$!
printf '%s\n' "$pid" >"$PIDFILE"

for _ in $(seq 1 40); do
  [ -f "$STATE/status.json" ] && break
  sleep 0.25
done

python2_bin="$(command -v python2.7 || command -v python2 || true)"
[ -n "$python2_bin" ] || { echo "INSTALL=FAIL missing_python2"; exit 2; }

if ! grep -q 'CONTINUITY_GIT_CONTROL_STATUS_V1' "$WSGI"; then
  backup="$WSGI.pre-continuity-git-control-$(date +%Y%m%dT%H%M%S).bak"
  cp -p "$WSGI" "$backup"

  python3 - "$WSGI" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
marker='CONTINUITY_GIT_CONTROL_STATUS_V1'
if marker in s:
    raise SystemExit(0)
needle='def application(environ, start_response):'
if needle not in s:
    raise SystemExit('application function not found')
helper=r'''
# CONTINUITY_GIT_CONTROL_STATUS_V1
CONTINUITY_STATUS_FILE = BASE + "/.continuity-control/status.json"

def continuity_git_control_status(start_response):
    try:
        with open(CONTINUITY_STATUS_FILE, "rb") as f:
            body = f.read(32768)
    except Exception:
        body = b'{"service":"continuity-git-control","state":"UNAVAILABLE"}\n'
    start_response("200 OK", [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "no-referrer"),
    ])
    return [body]

'''
s=s.replace(needle,helper+needle,1)
pathneedle='    path = environ.get("PATH_INFO", "/")\n'
route='''    path = environ.get("PATH_INFO", "/")\n\n    if path == "/__continuity_control/status":\n        return continuity_git_control_status(start_response)\n'''
if pathneedle not in s:
    raise SystemExit('PATH_INFO line not found')
s=s.replace(pathneedle,route,1)
p.write_text(s)
PY

  if ! "$python2_bin" -m py_compile "$WSGI"; then
    cp -p "$backup" "$WSGI"
    echo "INSTALL=FAIL passenger_syntax_rollback"
    exit 2
  fi
  rm -f "$WSGI"c 2>/dev/null || true
  mkdir -p "$BASE/tmp"
  touch "$BASE/tmp/restart.txt"
  echo "passenger_status_route=installed"
else
  echo "passenger_status_route=present"
fi

echo "agent_pid=$pid"
echo "agent_status_file=$STATE/status.json"
echo "public_status=https://www.powerpc-darwin.org/__continuity_control/status"
echo "INSTALL=PASS"
