# Secure MCP lifecycle supervisor

Status: VERSIONED / LIVE APPLY PENDING

Purpose: keep the existing OpenAI Secure MCP runtime `powerpc-local-mcp` independent of the Web Terminal/PTY lifecycle without replacing the local MCP or the tunnel.

## Correct lifecycle model

The stdio MCP at:

`<POWERPC_WEBAPP_ROOT>/bin/local-mcp`

remains a bounded stdio child. It is **not** converted into a network daemon.

The OpenAI `tunnel-client` owns the long-lived managed runtime. Current `tunnel-client` guidance distinguishes:

- `tunnel-client run --profile ...`: foreground daemon attached to the current terminal;
- `tunnel-client runtimes connect ...`: native detached managed runtime with PID/log/health state.

The keepalive therefore does **not** wrap `tunnel-client run` in `nohup` or `tmux`. It polls native runtime status and, only when unhealthy, calls `runtimes connect` against the already-existing tunnel ID.

## Files

- `secure-mcp-keepalive` — desired-state controller.
- `install-secure-mcp-keepalive.sh` — one-shot host installer.

Host targets:

- controller: `<POWERPC_WEBAPP_ROOT>/bin/secure-mcp-keepalive`
- private state: `<POWERPC_WEBAPP_ROOT>/.secure-mcp-keepalive/`
- runtime key: private `0600` file under that state directory
- tunnel-client binary hint: private file under that state directory

## Credential migration

The previously accepted runtime profile referenced `env:CONTROL_PLANE_API_KEY`. A cron invocation does not inherit the Web Terminal environment.

The installer therefore captures the **already-present host environment value** into a private `0600` file without printing it. It refuses to invent or expose a replacement key. If neither the existing private file nor the current host environment value is available, installation fails closed with:

`RUNTIME_KEY_MIGRATION=REQUIRED`

The keepalive reconnect uses only the file reference.

## Supervision

The host lacks a usable user-systemd bus. Supervision is therefore:

```
@reboot secure-mcp-keepalive ensure
* * * * * secure-mcp-keepalive ensure
```

The controller:

1. takes a single-instance `flock`;
2. calls `tunnel-client runtimes status powerpc-local-mcp --json`;
3. requires process/health/readiness evidence, or the loopback `/healthz` + `/readyz` surfaces for an older status schema;
4. never accepts legacy `runtime_state=ready` alone as durable-process proof;
5. reuses the exact existing `tunnel_id` when reconnecting;
6. uses native `runtimes connect`, not a second daemon model;
7. closes the supervisor lock descriptor before invoking tunnel-client so the managed child cannot inherit it;
8. keeps bounded private logs;
9. preserves an explicit persistent disabled state.

## Operator semantics

- `secure-mcp-keepalive status`
- `secure-mcp-keepalive enable`
- `secure-mcp-keepalive restart`
- `secure-mcp-keepalive stop`

`stop` writes the disabled marker before stopping the native runtime. Cron respects that marker.

## Acceptance

Do not classify lifecycle hardening complete until all of the following are observed on the live PowerPC runtime:

1. installer returns `SECURE_MCP_KEEPALIVE_INSTALL=PASS`;
2. `secure-mcp-keepalive status` returns `HEALTHY`;
3. `tunnel-client runtimes status powerpc-local-mcp --json` reports managed process health/readiness;
4. cron contains exactly one reboot and one periodic keepalive line;
5. the originating Web Terminal/PTTY is destroyed;
6. after that destruction and at least one watchdog interval, status remains healthy or is automatically restored to healthy;
7. a fresh origin can execute an MCP acceptance call and retrieve its result.

The final two requirements are intentionally stronger than host-process installation. They close the prior false-completion gap:

`HOST READY != FRESH-SESSION CALLABLE`

`TEMPORARY SHELL SURVIVAL != DURABLE SUPERVISION`
