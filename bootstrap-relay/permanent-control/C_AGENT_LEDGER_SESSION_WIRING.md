# Continuity-Agent ledger session wiring

Status: `IMPLEMENTED ON RECEIVER BRANCH / LIVE ACCEPTANCE PENDING`

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
