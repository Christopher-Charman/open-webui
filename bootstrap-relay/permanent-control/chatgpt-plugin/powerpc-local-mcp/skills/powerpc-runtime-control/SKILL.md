---
name: powerpc-runtime-control
description: Inspect, diagnose, maintain, deploy to, or operate the powerpc-darwin.org managed runtime, including ChatGPT and iOS access through its existing owned GitHub transport and bounded MCP tools.
---

# powerpc-darwin.org runtime control

The existing primary route is the owned GitHub queue and encrypted HTTPS result transport into the runtime's local MCP. Read [Owned connection and execution](references/owned-connection.md) before sending a request. Use the authenticated GitHub connector for repository writes. Prefer the encrypted direct-origin route when execution and HTTPS are available; the Actions adapter is only for public-safe operations.

Do not assume a native server named `powerpc-control` is exposed: this package intentionally has empty MCP declarations. The saved optional Secure MCP Tunnel is not a prerequisite for the working owned route. Do not use Desktop Commander, rebuild the receiver, or invent a public MCP URL merely because native MCP tools are absent. Resolve the owned route first and report the specific missing capability if this session cannot use it.

## Runtime identity

Treat these as the durable identity binding for PowerPC runtime work:

- canonical project/runtime label: `fasthost.powerpc_darwin_org`
- legacy wire protocol runtime identifier: `fasthost.powerpc` (preserved for protocol compatibility)
- Unix identity: `<POWERPC_UNIX_USER>`
- UID: `2257347`
- GID: `500`
- namespace root: `<POWERPC_NAMESPACE_ROOT>`
- webapp root: `<POWERPC_WEBAPP_ROOT>`
- managed runtime host: `hp3-rr-1024747.hostingp3.local`
- provider SSH gateway host: `hp3-ssh.hostingp3.local`

Public/provider service addresses:

- web: `77.68.64.13`
- SSH: `<PROVIDER_SSH_ENDPOINT>`
- SFTP: `77.68.64.36`
- FTP/content: `<PROVIDER_TRANSFER_ENDPOINT>`

Known loopback services on the managed runtime:

- OpenWebUI: `127.0.0.1:18080`
- broker: `127.0.0.1:18081`
- TTS: `127.0.0.1:18082`
- Pocket: `127.0.0.1:18083`
- Open Terminal: `127.0.0.1:9900`
- terminal gateway: `127.0.0.1:19900`
- Ollama: `127.0.0.1:11434`
- g4f MCP lineage: `127.0.0.1:8765/mcp`
- historical bootstrap-control lineage: `127.0.0.1:18765`
- historical internal management sshd: `127.0.0.1:2222`

## Existing MCP tool contract

The canonical local MCP is:

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

## Namespace separation: Evenio

Never infer that shared Fasthost front doors imply shared identity or authority.

Evenio is independent:

- runtime label: `fasthost.evenio`
- Unix identity: `<EVENIO_UNIX_USER>`
- UID: `2283676`
- GID: `500`
- namespace root: `<EVENIO_NAMESPACE_ROOT>`
- managed application node may also be `hp3-rr-1024747.hostingp3.local`, but under the separate Unix identity
- SSH gateway: `<PROVIDER_SSH_ENDPOINT>` -> `hp3-ssh.hostingp3.local`
- content/transfer endpoint: `<PROVIDER_TRANSFER_ENDPOINT>`
- local inference endpoint: `127.0.0.1:11435`

The SSH gateway namespace is not the Passenger managed-runtime namespace. Matching provider hosts or public service IPs never merge PowerPC and Evenio credentials, filesystems, mutable runtime state, or project authority.

## Security and secrets

This plugin contains no API keys, bearer tokens, cookies, passwords, or private keys. Repository write authorization gates the owned queue; commands and receipts use the existing X25519/AES-GCM and Ed25519 protocol. Keep private origin context and decrypted output out of Git, public artifacts and chat unless the user needs the output. The public Actions adapter stores plaintext requests and results: never send sensitive data through it. Optional tunnel credentials remain on the host.

If a request would expose or rotate a secret, perform only the minimum necessary operation and never echo secret material back into chat unless the user explicitly asks for the secret itself.
