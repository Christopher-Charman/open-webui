# Owned PowerPC control — fresh-origin acceptance runbook

Status: VERSIONED / LIVE EXECUTION PENDING

This runbook begins only after `bootstrap-control-plane.sh` reports that the owned receiver host phase passed. It is intentionally origin-side: the Web Terminal must no longer be used as routine command or output transport.

## Required surfaces

- GitHub connector with write access to `Christopher-Charman/open-webui`;
- public HTTPS read access to the PowerPC identity/result carrier;
- a local Python 3 environment with `cryptography` for the deterministic `origin-client.py`.

Canonical queue:

`bootstrap-relay/permanent-control/queue.json`

Runtime identity:

`https://www.powerpc-darwin.org/.well-known/powerpc-control-v1/identity.json`

Runtime status:

`https://www.powerpc-darwin.org/.well-known/powerpc-control-v1/status.json`

Result template:

`https://www.powerpc-darwin.org/.well-known/powerpc-control-v1/results/<task_id>.json`

## Fresh-origin positive acceptance

1. Start from a fresh assistant conversation/session.
2. Recover the canonical SOUL/control-plane surfaces and this runbook.
3. Retrieve `identity.json` and verify:
   - protocol `powerpc-control-v1`;
   - runtime `fasthost.powerpc`;
   - UID `2257347`;
   - signature verifies through `origin-client.py`.
4. Generate an encrypted, harmless `list_dir` request for the bounded webapp root. This is the primary transport-liveness probe because it does not depend on unrelated platform-health checks or a guessed file name.
5. Fetch current `queue.json` through GitHub, append the generated task object without altering unrelated live tasks, and commit it.
6. Poll only the expected result path. Allow up to 240 seconds for the current public-static receipt path; observed receipt publication can exceed 100 seconds. Do not treat heartbeat or queue observation as execution success.
7. Decode/verify the signed encrypted result and require:
   - `completion_state=COMPLETED`;
   - executor/runtime identity bound to `fasthost.powerpc`;
   - exactly one `list_dir` local-MCP action;
   - non-empty bounded text result.
8. Prove duplicate suppression against that completed envelope by checking the result bytes and `published_at` remain unchanged after additional receiver polling cycles.
9. Repeat with `read_text` against the long-established live controller `passenger_wsgi.py`, requiring `completion_state=COMPLETED` and non-empty text.
10. Repeat with one bounded non-destructive `terminal_exec` under `bounded_operator`, requiring `completion_state=COMPLETED`.

`runtime_health` remains available as a platform-health diagnostic, but it executes the wider architecture-health script and is not the owned-transport liveness gate. A degraded or slow unrelated service must not be misclassified as communication-path failure.

Invariant: `CONTROL_TRANSPORT_ACCEPTANCE != AGGREGATE_RUNTIME_HEALTH`.

## Duplicate suppression

Use an already-completed task object byte-for-byte with the same `task_id`.

Expected result:
- no second local-MCP execution;
- existing terminal receipt remains authoritative;
- receiver task state remains one logical execution.

A second successful execution is a failure.

## Expiry

Prepare a valid encrypted task whose outer `expires_at` is already in the past by the time the receiver observes it.

Expected terminal state:
`EXPIRED`

No local-MCP action is permitted.

## Authority attenuation

Prepare `terminal_exec` with:
`authority_ceiling=read_only`

Expected terminal state:
`NEEDS_AUTHORITY`

No terminal action is permitted.

## Fail-closed controls

At least one test in each class:

- target runtime mismatch;
- capability profile excludes requested tool;
- task ID conflict with different ciphertext;
- corrupt ciphertext/signature material.

Expected:
- no unauthorized local execution;
- bounded reject/failure evidence;
- no widening of the local MCP contract.

## Web-Terminal independence

Before declaring the transport permanent:

1. destroy the exact Web Terminal/PTTY used for bootstrap;
2. wait at least one watchdog interval;
3. verify the owned receiver heartbeat changed after terminal destruction;
4. if Secure MCP lifecycle hardening was installed, require its managed runtime to remain or recover healthy independently;
5. run a new fresh-origin `runtime_health` task after destruction.

## C-Agent receiver gate

The transport is not the full inter-agent control plane until a delegated synthetic task proves:

`origin -> owned ingress -> validated task -> receiver claim -> continuity-agent invocation -> bounded local action -> durable terminal receipt -> origin retrieval`

The claim/result record must preserve `task_id`, executor identity, runtime receipt, effective authority, actions, evidence refs, unresolved state, resource usage, and completion state.

## Completion boundary

Only after every positive and negative acceptance passes may the durable state be promoted to:

`PERMANENT_ACCESS=ACCEPTED`

and, separately after the C-Agent chain:

`INTER_AGENT_CONTROL_PLANE=ACCEPTED`

A host install, healthy heartbeat, successful single command, or surviving process is insufficient by itself.
