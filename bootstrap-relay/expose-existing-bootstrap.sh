#!/usr/bin/env bash
set -euo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
CTRL="$BASE/passenger_wsgi.py"
STATE="$BASE/.chatgpt-bootstrap"
PORT="18765"
PREFIX="/__cgpt-bootstrap-208f5ba5e1b54083"
MARK_BEGIN="# BEGIN CHATGPT TEMP BOOTSTRAP PROXY 20260929"

fail() {
  printf 'BOOTSTRAP_PROXY=FAIL\nreason=%s\n' "$1" >&2
  exit 1
}

[ "$(id -u)" = "2257347" ] || fail "unexpected_uid"
[ "$PWD" = "$BASE" ] || cd "$BASE" || fail "cannot_enter_webapp"
[ -f "$CTRL" ] || fail "missing_passenger_wsgi"
[ -f "$STATE/bootstrap.pid" ] || fail "missing_bootstrap_pid"

BPID="$(cat "$STATE/bootstrap.pid" 2>/dev/null || true)"
[ -n "$BPID" ] && kill -0 "$BPID" 2>/dev/null || fail "bootstrap_server_not_running"

code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:$PORT/" || true)"
[ "$code" = "404" ] || fail "bootstrap_server_not_reachable"

if grep -Fq "$MARK_BEGIN" "$CTRL"; then
  printf 'BOOTSTRAP_PROXY=ALREADY_PRESENT\n'
else
  TS="$(date +%Y%m%d-%H%M%S)"
  BACKUP="$CTRL.pre-chatgpt-bootstrap-$TS"
  cp -p "$CTRL" "$BACKUP"

  cat >> "$CTRL" <<'PYWRAP'

# BEGIN CHATGPT TEMP BOOTSTRAP PROXY 20260929
# Temporary, capability/HMAC-protected ingress to the already-running
# loopback bootstrap controller. GET only; no cookies or browser auth forwarded.
import httplib as _cgpt_httplib

_CGPT_BOOTSTRAP_PREFIX = '/__cgpt-bootstrap-208f5ba5e1b54083'
_CGPT_BOOTSTRAP_PORT = 18765
_cgpt_previous_application = application

def _cgpt_bootstrap_proxy(environ, start_response):
    method = environ.get('REQUEST_METHOD', 'GET').upper()
    if method != 'GET':
        body = 'method not allowed\n'
        start_response('405 Method Not Allowed', [
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Length', str(len(body))),
            ('Cache-Control', 'no-store'),
            ('Allow', 'GET'),
        ])
        return [body]

    path = environ.get('PATH_INFO', '')
    local_path = path[len(_CGPT_BOOTSTRAP_PREFIX):] or '/'
    query = environ.get('QUERY_STRING', '')
    if query:
        local_path += '?' + query

    conn = None
    try:
        conn = _cgpt_httplib.HTTPConnection('127.0.0.1', _CGPT_BOOTSTRAP_PORT, timeout=50)
        conn.request('GET', local_path, headers={'Host': '127.0.0.1', 'Connection': 'close'})
        resp = conn.getresponse()
        data = resp.read(131072)
        ctype = resp.getheader('Content-Type') or 'application/json'
        start_response('%d %s' % (resp.status, resp.reason), [
            ('Content-Type', ctype),
            ('Content-Length', str(len(data))),
            ('Cache-Control', 'no-store'),
            ('X-Content-Type-Options', 'nosniff'),
        ])
        return [data]
    except Exception:
        body = 'bootstrap proxy unavailable\n'
        start_response('502 Bad Gateway', [
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Length', str(len(body))),
            ('Cache-Control', 'no-store'),
        ])
        return [body]
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

def application(environ, start_response):
    path = environ.get('PATH_INFO', '')
    if path == _CGPT_BOOTSTRAP_PREFIX or path.startswith(_CGPT_BOOTSTRAP_PREFIX + '/'):
        return _cgpt_bootstrap_proxy(environ, start_response)
    return _cgpt_previous_application(environ, start_response)
# END CHATGPT TEMP BOOTSTRAP PROXY 20260929
PYWRAP

  PY2="$(command -v python2.7 || command -v python2 || true)"
  if [ -z "$PY2" ]; then
    cp -p "$BACKUP" "$CTRL"
    fail "python2_missing_for_syntax_check"
  fi

  if ! "$PY2" - "$CTRL" <<'PYCHECK'
import ast, sys
p = sys.argv[1]
with open(p, 'rb') as f:
    ast.parse(f.read(), filename=p)
PYCHECK
  then
    cp -p "$BACKUP" "$CTRL"
    fail "passenger_syntax_check_failed_rolled_back"
  fi

  printf '%s\n' "$BACKUP" > "$STATE/passenger-bootstrap-backup.path"
fi

mkdir -p "$BASE/tmp"
touch "$BASE/tmp/restart.txt"

PUBLIC="https://www.powerpc-darwin.org$PREFIX/"
status=""
for _ in $(seq 1 30); do
  status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$PUBLIC" || true)"
  [ "$status" = "404" ] && break
  sleep 1
done

printf 'BOOTSTRAP_PROXY=STAGED\n'
printf 'public_prefix=https://www.powerpc-darwin.org%s\n' "$PREFIX"
printf 'local_controller=127.0.0.1:%s\n' "$PORT"

if [ "$status" = "404" ]; then
  printf 'public_proxy=PASS\n'
  printf 'restart_required=NO\n'
else
  printf 'public_proxy=PENDING\n'
  printf 'restart_required=YES\n'
  printf 'observed_http=%s\n' "$status"
fi
