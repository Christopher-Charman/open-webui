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
4. Generate an encrypted `runtime_health` request:
   ```
   origin-client.py prepare \
     --identity identity.json \
     --tool runtime_health \
     --arguments '{}' \
     --authority read_only \
     --output task.json \
     --context task.context.json
   ```
5. Fetch current `queue.json` through GitHub, append the generated task object without altering unrelated live tasks, and commit it.
6. Poll only the expected result path. Do not treat heartbeat or queue observation as execution success.
7. Decode/verify:
   ```
   origin-client.py decode \
     --result result.json \
     --context task.context.json \
     --output receipt.json
   ```
8. Require a signature-verified, decryptable runtime receipt bound to `fasthost.powerpc`, with exactly one `runtime_health` local-MCP action. `completion_state=COMPLETED` means the aggregate architecture-health probe is healthy; `completion_state=FAILED` is also a valid control-transport round trip when the returned MCP result has `isError=true`. Record that live health degradation separately; do not misclassify it as transport failure.
9. Repeat with `read_text` against one harmless allowed file and require `completion_state=COMPLETED`.
10. Repeat with one bounded non-destructive `terminal_exec` under `bounded_operator` and require `completion_state=COMPLETED`.

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
