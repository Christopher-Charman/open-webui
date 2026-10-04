# Continuity-Agent ledger session wiring

Status: `LIVE ACCEPTED 2026-10-04 / SESSION LAYER ONLY`

The Continuity-Agent delegation receiver now participates in the authoritative
Concurrency Ledger at the **session layer only**.

Before any model admission call or local-MCP action, the receiver:

1. resolves the deployed private Concurrency-Ledger C-Agent adapter;
2. authenticates through the dedicated
   `concurrency-ledger-cagent-call` client;
3. opens a role-free session as `actor:continuity-agent` on
   `openwebui:continuity-agent`;
4. heartbeats that session;
5. records the returned session and heartbeat facts in its delegation receipt.

If any of those steps cannot be established, delegation fails closed before
model or tool execution.

## Receiver model identity

The delegation receiver's accepted claim-model identity is
`qwen2.5-coder:1.5b-instruct-q4_K_M`. It is now resolved from the receiver
implementation itself and verified against the live Ollama inventory.

The mutable OpenWebUI `continuity-agent` model-preset row is **not** receiver
lifecycle authority. UI/preset experiments may therefore change or disable that
row without silently changing the accepted inter-agent receiver model. A future
receiver-model change requires an explicit reviewed implementation/configuration
delta and fresh acceptance.

## Live acceptance — 2026-10-04

The deployed receiver is now accepted for the bounded session-layer integration.

Acceptance evidence:

- exact receiver source from `open-webui@ad7dbddcded9799c5a6b167cd74a9d97aa715d85` was installed and verified byte-for-byte by SHA-256;
- the deployed executable uses the supported Python 3.12 interpreter and passed its self-test;
- all six focused ledger receiver regression tests passed;
- a fresh read-only `runtime_health` delegation completed through the real receiver with exactly two ledger calls, one model claim and one local-MCP call;
- the receipt contained one ledger-session fact, one ledger-heartbeat fact and one claim digest;
- replaying the identical envelope returned the identical durable receipt without rewriting the receiver record;
- the returned session was independently found in the live ledger as `actor:continuity-agent` on `openwebui:continuity-agent`, status `ACTIVE`, with a persisted heartbeat and no role assignment.

Receipt: `C_AGENT_LEDGER_SESSION_ACCEPTANCE_20261004.json`.

`LIVE SESSION ACCEPTANCE != ROLE AUTHORITY != TASK OWNERSHIP`.

## Authority boundary

This change deliberately does **not** grant or infer:

- a role assignment;
- project-scoped read authority;
- task ownership or an ownership epoch;
- a ledger task claim;
- a run binding;
- a lease or fencing token;
- mutation authority.

Those require separate authoritative bindings and acceptance.

A successful session proves authenticated C-Agent participation and liveness,
not permission to act on a project or task.

## Retry semantics

Ledger session open and heartbeat use deterministic idempotency keys derived
from the delegation task ID. Existing delegation record replay remains the
outer duplicate-suppression boundary: a completed identical envelope returns
its existing receipt without opening another session, invoking the model, or
re-executing local MCP.

`SESSION PARTICIPATION != ROLE AUTHORITY != TASK OWNERSHIP`.
