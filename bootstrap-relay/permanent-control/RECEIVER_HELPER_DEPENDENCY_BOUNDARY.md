# Receiver helper dependency boundary

Status: SOURCE CANDIDATE / NOT LIVE-DEPLOYED BY THIS BRANCH

The owned `powerpc-control-v1` receiver helper must not import the MCP SDK from Desktop Commander's private installation tree.

Canonical dependency source:

`/home/storage/781/4477781/user/webapp/runtime-domains/local-mcp/node_modules/@modelcontextprotocol/sdk`

This deliberately couples the receiver helper to the owned local-MCP package boundary introduced by repository-prime PR #9, rather than to recovery tooling.

## Required live gate

Before applying this helper source to `/home/storage/781/4477781/user/.powerpc-control-v1/local-mcp-call.mjs`:

1. local-MCP package-local dependencies must exist and pass `npm ci`;
2. `/webapp/bin/local-mcp` must pass four-tool discovery;
3. helper syntax must pass under the host Node 22 runtime;
4. one receiver `runtime_health` round trip must pass through the updated helper;
5. rollback copy of the previous helper must remain available until that receipt verifies.

No Desktop Commander fallback is permitted. Missing package-local dependencies must fail closed.
