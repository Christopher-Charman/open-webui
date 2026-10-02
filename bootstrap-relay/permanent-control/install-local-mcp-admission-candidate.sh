#!/bin/sh
set -eu
umask 077

ACCOUNT="/home/storage/781/4477781/user"
WEBAPP="$ACCOUNT/webapp"
RUNTIME_ROOT="$WEBAPP/runtime-domains"
LIVE="$RUNTIME_ROOT/local-mcp"
STATE="$ACCOUNT/.powerpc-control-v1"
HELPER="$STATE/local-mcp-call.mjs"
NODE="$WEBAPP/.local/node22-glibc217/bin/node"
NPM="$WEBAPP/.local/node22-glibc217/bin/npm"
PAYLOAD_COMMIT="3865462be666815465a5cccb03cfcdbdd89a00bb"
BASE="https://raw.githubusercontent.com/Christopher-Charman/open-webui/$PAYLOAD_COMMIT/bootstrap-relay/permanent-control"
CANDIDATE_BASE="$BASE/local-mcp-admission-candidate"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
STAGE="$RUNTIME_ROOT/.local-mcp-admission-$STAMP"
BACKUP="$RUNTIME_ROOT/local-mcp.pre-admission-$STAMP"
HELPER_BACKUP="$STATE/local-mcp-call.mjs.pre-admission-$STAMP"
FAILED_COPY="$RUNTIME_ROOT/.local-mcp-failed-$STAMP"
SWAPPED=0
SUCCESS=0

fail() {
  echo "LOCAL_MCP_ADMISSION_DEPLOY=FAIL reason=$1" >&2
  exit 1
}

rollback() {
  rc=$?
  if [ "$SUCCESS" = "1" ]; then
    exit "$rc"
  fi
  if [ "$SWAPPED" = "1" ]; then
    if [ -d "$LIVE" ]; then
      mv "$LIVE" "$FAILED_COPY" 2>/dev/null || true
    fi
    if [ -d "$BACKUP" ]; then
      mv "$BACKUP" "$LIVE" 2>/dev/null || true
    fi
    if [ -f "$HELPER_BACKUP" ]; then
      cp -p "$HELPER_BACKUP" "$HELPER" 2>/dev/null || true
      chmod 700 "$HELPER" 2>/dev/null || true
    fi
  fi
  [ -d "$STAGE" ] && rm -rf "$STAGE" || true
  echo "LOCAL_MCP_ADMISSION_ROLLBACK=APPLIED rc=$rc" >&2
  exit "$rc"
}
trap rollback EXIT INT TERM

[ "$(id -u)" = "2257347" ] || fail "runtime_identity"
[ -d "$WEBAPP" ] || fail "webapp_missing"
[ -d "$LIVE" ] || fail "live_local_mcp_missing"
[ -x "$WEBAPP/bin/local-mcp" ] || fail "launcher_missing"
[ -x "$NODE" ] || fail "node22_missing"
[ -x "$NPM" ] || fail "npm_missing"
[ -f "$HELPER" ] || fail "receiver_helper_missing"
[ ! -e "$STAGE" ] && [ ! -e "$BACKUP" ] || fail "staging_collision"

mkdir -p "$STAGE"

for f in server.mjs client-smoke.mjs path-policy.mjs path-policy.test.mjs package.json package-lock.json DEPENDENCY_PROVENANCE.json SOURCE_VALIDATION_RECEIPT_2026-09-30.md; do
  curl -fsSL --retry 4 --connect-timeout 10 "$CANDIDATE_BASE/$f" -o "$STAGE/$f" || fail "download_$f"
done
curl -fsSL --retry 4 --connect-timeout 10 "$BASE/local-mcp-call.mjs" -o "$STAGE/receiver-helper.mjs" || fail "download_receiver_helper"

grep -Fq "createBoundedPathResolver" "$STAGE/server.mjs" || fail "path_policy_marker_missing"
if grep -Fq "desktop-commander-remote" "$STAGE/server.mjs" "$STAGE/receiver-helper.mjs"; then
  fail "desktop_commander_dependency_present"
fi

"$NODE" --check "$STAGE/server.mjs" || fail "server_syntax"
"$NODE" --check "$STAGE/client-smoke.mjs" || fail "client_syntax"
"$NODE" --check "$STAGE/path-policy.mjs" || fail "path_policy_syntax"
"$NODE" --check "$STAGE/path-policy.test.mjs" || fail "path_policy_test_syntax"
"$NODE" --check "$STAGE/receiver-helper.mjs" || fail "receiver_helper_syntax"

(
  cd "$STAGE"
  "$NPM" ci --ignore-scripts --no-audit --no-fund
  "$NPM" run check:syntax
  "$NPM" run test:path-policy
) || fail "npm_ci_or_source_tests"

cat >"$STAGE/stage-smoke.mjs" <<'NODE'
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport, getDefaultEnvironment } from '@modelcontextprotocol/sdk/client/stdio.js';

const root='/home/storage/781/4477781/user/webapp';
const server=process.argv[2];
const node=process.argv[3];
const c=new Client({name:'local-mcp-admission-stage',version:'1.0.0'},{capabilities:{}});
const t=new StdioClientTransport({
  command:node,
  args:[server],
  cwd:root,
  env:{...getDefaultEnvironment(),HOME:'/home/storage/781/4477781/user'}
});
try {
  await c.connect(t);
  const tools=(await c.listTools()).tools.map(x=>x.name).sort();
  const expected=['list_dir','read_text','runtime_health','terminal_exec'];
  if (JSON.stringify(tools)!==JSON.stringify(expected)) throw new Error('tool_contract_mismatch:'+JSON.stringify(tools));
  const read=await c.callTool({name:'read_text',arguments:{path:'CONTROL_PLANE.md',max_bytes:128}});
  if (read.isError) throw new Error('read_text_failed');
  const term=await c.callTool({name:'terminal_exec',arguments:{command:'printf LOCAL_MCP_STAGE_OK',timeout_ms:2000}});
  const text=(term.content||[]).map(x=>x.text||'').join('\n');
  if (term.isError || !text.includes('LOCAL_MCP_STAGE_OK')) throw new Error('terminal_exec_stage_failed');
  console.log('LOCAL_MCP_STAGE_SMOKE=PASS');
} finally {
  try { await c.close(); } catch {}
  try { await t.close(); } catch {}
}
NODE

(
  cd "$STAGE"
  "$NODE" "$STAGE/stage-smoke.mjs" "$STAGE/server.mjs" "$NODE"
) || fail "stage_mcp_smoke"

cp -p "$HELPER" "$HELPER_BACKUP"
chmod 600 "$HELPER_BACKUP"

mv "$LIVE" "$BACKUP"
mv "$STAGE" "$LIVE"
cp "$LIVE/receiver-helper.mjs" "$HELPER.new"
chmod 700 "$HELPER.new"
mv -f "$HELPER.new" "$HELPER"
SWAPPED=1

(
  cd "$LIVE"
  "$NPM" run check:syntax
  "$NPM" run test:path-policy
  "$NODE" "$LIVE/client-smoke.mjs"
) || fail "live_local_mcp_smoke"

printf '%s' '{"tool":"read_text","arguments":{"path":"CONTROL_PLANE.md","max_bytes":64}}' |
  "$NODE" "$HELPER" >"$STATE/local-mcp-helper-smoke-$STAMP.json" || fail "receiver_helper_smoke"
"$NODE" - "$STATE/local-mcp-helper-smoke-$STAMP.json" <<'NODE' || fail "receiver_helper_result"
import fs from 'node:fs';
const d=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
if (d.isError) process.exit(1);
const text=(d.content||[]).map(x=>x.text||'').join('\n');
if (!text) process.exit(1);
NODE

if grep -Fq "desktop-commander-remote" "$LIVE/server.mjs" "$HELPER"; then
  fail "live_desktop_commander_dependency_present"
fi

SERVER_SHA256="$(sha256sum "$LIVE/server.mjs" | awk '{print $1}')"
HELPER_SHA256="$(sha256sum "$HELPER" | awk '{print $1}')"
LOCK_SHA256="$(sha256sum "$LIVE/package-lock.json" | awk '{print $1}')"

SUCCESS=1
trap - EXIT INT TERM

echo "LOCAL_MCP_ADMISSION_DEPLOY=PASS"
echo "payload_commit=$PAYLOAD_COMMIT"
echo "server_sha256=$SERVER_SHA256"
echo "receiver_helper_sha256=$HELPER_SHA256"
echo "package_lock_sha256=$LOCK_SHA256"
echo "backup=$BACKUP"
echo "helper_backup=$HELPER_BACKUP"
echo "rollback=AVAILABLE"
echo "receiver_restart=NOT_REQUIRED"
