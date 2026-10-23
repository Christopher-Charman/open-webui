---
name: powerpc-runtime-control
description: Inspect, diagnose, maintain, deploy to, or operate the powerpc-darwin.org managed runtime, through the existing owner-approved transport and bounded MCP tools.
---

# PowerPC runtime control (public-safe reference)

Use the registered, authenticated owner executor and private owner registry to select the operation-specific runtime route. Public GitHub source is not a credential store or runtime identity registry. Keep public repository carriers restricted to approved public-safe operations and summary-only results.

This source package intentionally declares no native MCP endpoint. Resolve available authenticated owner executors from the private capability registry, rather than inventing a public MCP endpoint or interpreting the absence of one transport as a lack of runtime access.

## Runtime identity

Resolve the exact runtime, user/UID, filesystem namespace, host, service addresses and protocol identifiers from the current **private owner registry** for each operation. This public fork intentionally contains no owner runtime identifiers or addresses. A runtime label alone is not authorization or liveness evidence.

## Existing MCP tool contract

The canonical local MCP is resolved from the private owner registry:

`PPC_WEBAPP_ROOT/bin/local-mcp`

Expected bounded tools:

- `runtime_health`
- `read_text`
- `list_dir`
- `terminal_exec`

Do not recreate these tools or widen their authority. The local MCP owns the filesystem root, UID, timeout, output, and shell-execution boundaries.

## Operating sequence

For execution-sensitive work:

1. Call `runtime_health` first unless the current task already has fresh live health evidence.
2. Use `read_text` and `list_dir` for inspection before mutation when practical.
3. Use `terminal_exec` only for bounded commands necessary to the user's requested task.
4. Preserve the current Unix identity and namespace; never use privilege escalation.
5. Keep unrelated services running unless a specific verified change requires a restart.
6. After mutation, rerun the smallest relevant health/regression checks.

Live runtime evidence governs mutable process/service state. Git and Shared Library are durable history/currentness projections, not substitutes for fresh runtime evidence when the current state matters.

## Namespace separation: other runtimes

Never infer shared identity or authority from a common provider, host or public address. Each runtime's identity, namespace, endpoints and credentials belong in the private owner registry and must be freshly resolved for the requested operation.

## Security and secrets

Do not publish credentials, private keys, runtime identifiers, decrypted output, control receipts, or provider-specific endpoints through this fork. Preserve the established encryption and signature protections on the authorised private transport. Public repository carriers must use their separately verified public-safe and summary-only contract. Secrets and mutable runtime bindings remain with the private owner.

If a request would expose or rotate a secret, perform only the minimum necessary operation and never echo secret material back into chat unless the user explicitly asks for the secret itself.
