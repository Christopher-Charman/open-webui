# OpenWebUI recovery read-only probe staging — 2026-09-30

Status: STAGED / NOT EXECUTED / NO LIVE RUNTIME MUTATION

Branch:
`recovery/openwebui-readonly-probe-20260930`

Base:
`2ea75e732bcb2b9e95039f342e50404c2ffbbd59`

Probe:
`bootstrap-relay/recovery-runtime-probe-20260930/probe-v2.py`

Probe staging commit:
`2c728e6de96bbc3c2030480085ab653c4724effb`

## Reason for v2

The earlier encrypted recovery transaction reached the verified `fasthost.powerpc` receiver and returned a signed/decryptable failure receipt, but local MCP rejected `terminal_exec timeout_ms=90000` because the bounded tool contract permits at most 30000 ms.

The earlier shell probe also contained serial network/public checks whose worst-case duration could exceed that 30-second ceiling.

v2 therefore:
- remains read-only;
- is Python stdlib-only on-host;
- probes loopback listeners/HTTP concurrently;
- inspects OpenWebUI/Ollama configuration and model binding through read-only SQLite;
- hashes deployed presentation/voice assets;
- scans voice startup code for audible warm/playback triggers;
- omits external/public verification from the host transaction;
- is intended for `terminal_exec timeout_ms=30000`.

## Concurrency hold

At staging time another session owned the permanent-control queue with:
`ppc-canonical-health-1790801465`

Created:
`2026-09-30T20:51:05Z`

Expiry:
`2026-09-30T21:06:05Z`

No additional queue task was appended while that transaction remained live.

The public signed identity was independently retrieved and verified:
- runtime: `fasthost.powerpc`
- user: `csh3280350`
- uid: `2257347`
- hostname: `hp3-rr-1024747.hostingp3.local`
- identity fingerprint: `SHA256:l7SrivQiY5uhxagCB/L9SR7IvXH3EKcP33HdEgeBaRI`
- state: `ready`

## Next safe transaction

After confirming no newer concurrent queue owner:
1. refresh signed identity;
2. generate one encrypted `terminal_exec` envelope locally;
3. command: fetch immutable `probe-v2.py` and run it with the OpenWebUI Python;
4. set `timeout_ms=30000`;
5. append to the current queue using current queue blob/version evidence;
6. retrieve signed task-scoped receipt;
7. verify signature and decrypt;
8. classify Ollama -> config -> inventory -> preset binding, voice trigger, and deployed presentation identity before any repair mutation.

Do not deploy the accepted-stack restore until this read-only convergence is reviewed.
