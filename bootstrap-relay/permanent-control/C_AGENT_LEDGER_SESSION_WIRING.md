# Continuity-Agent ledger session wiring

Status: `SESSION + PROJECT-FRONTIER + SEEDED ADMISSION LAYERS LIVE ACCEPTED / TASK OWNERSHIP NOT GRANTED`

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

Admission sampling is also pinned by the receiver implementation:
`CLAIM_MODEL_SEED = 42`. This controls reproducibility only; it does not widen
the admitted capability set or relax the CLAIM/DECLINE policy.

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

## Project-frontier consumption implementation

The receiver now has an implementation path for the separately accepted
`LEDGER_PROJECT_READ` assignment:

- assignment:
  `assignment:continuity-agent:concurrency.orchestration:read`;
- project: `concurrency.orchestration`;
- exact role-scoped read: `ledger_frontier_get`;
- bounded limit: 10;
- execution order: session open -> session heartbeat -> frontier read -> model
  admission -> local-MCP execution.

The frontier is validated before model/tool execution. The receiver requires
both `SUMMARY_IS_NOT_AUTHORITY` and
`READY_UNCLAIMED_IS_NOT_CLAIM_ADMISSION` and records only a
`ledger_frontier_sha256:<digest>` evidence fact.

The frontier is **not** supplied to the claim model and is not converted into
task ownership, claim admission, run/lease authority or destination mutation
authority. Failure to establish the authorized bounded read fails closed before
model/tool execution.

Focused source regression tests pass and the legacy 1 October delegation
acceptance fingerprint remains unchanged.

### Live frontier acceptance — 2026-10-04

Merged source `open-webui@197277c6049c9fe217fc1ba45a954018f472864b`
was installed byte-for-byte as the live receiver and verifier. The receiver
self-test passed and live `cagent-status` retained the accepted 1 October
fingerprint.

Fresh real receiver executions proved the pre-admission sequence:

1. open dedicated Continuity-Agent ledger session;
2. heartbeat the session;
3. perform the bounded project `ledger_frontier_get`;
4. record exactly one `ledger_frontier_sha256:<digest>`;
5. reach the existing model-admission step only after the frontier read.

The final acceptance task
`cagent-frontier-live-final-20261004T232905` recorded exactly three ledger
calls, one model call and no local-MCP call because the independent claim model
returned `DECLINE`. The durable receipt remained `BLOCKED /
agent_declined`, which preserves admission semantics rather than bypassing
them. An identical replay returned the same receipt byte-for-byte without
opening another session, rereading the frontier or reinvoking the model.

The acceptance session and active reader assignment were independently read
back from the live ledger, and the Continuity-Agent still had no task-ownership
rows. The same exact model claim input later returned `CLAIM` in an isolated
diagnostic. That separate claim-decision reproducibility defect was subsequently
reproduced as 5 CLAIM / 1 DECLINE across six identical unseeded live requests
and repaired on 2026-10-05 by pinning the Ollama admission seed to `42`
without changing the prompt, model, authority policy, capability policy,
temperature, context limit or output limit.

The deployed seeded receiver then returned 6 CLAIM / 0 DECLINE across six
identical live admissions, completed a fresh end-to-end
session -> heartbeat -> frontier -> seeded model -> local-MCP delegation, and
returned the identical durable receipt on replay without re-execution. The
legacy inter-agent acceptance fingerprint remained unchanged.

Frontier receipt:
`C_AGENT_FRONTIER_CONSUMPTION_ACCEPTANCE_20261004.json`.

Determinism receipt:
`C_AGENT_ADMISSION_DETERMINISM_ACCEPTANCE_20261005.json`.

`FRONTIER_CONSUMED_BEFORE_MODEL != TASK_OWNER`.

`DETERMINISTIC_ADMISSION != AUTHORITY_EXPANSION`.

## Authority boundary

The receiver now **uses** the separately accepted project-reader assignment:

- `assignment:continuity-agent:concurrency.orchestration:read`;
- authority ceiling `LEDGER_PROJECT_READ`;
- exact scope `project:concurrency.orchestration:read`.

This integration does not widen that grant and still does **not** grant or
infer:

- task ownership or an ownership epoch;
- a ledger task claim/release;
- a run binding;
- a lease or fencing token;
- destination-project/runtime mutation authority.

Those require separate authoritative bindings and acceptance.

A successful frontier read proves only bounded coordination-state visibility.
It does not authorize acting on a summarized task.

## Retry semantics

Ledger session open and heartbeat use deterministic idempotency keys derived
from the delegation task ID. Existing delegation record replay remains the
outer duplicate-suppression boundary: any durable identical envelope returns
its existing receipt without opening another session, rereading the frontier,
invoking the model, or re-executing local MCP.

`SESSION PARTICIPATION != ROLE AUTHORITY != TASK OWNERSHIP`.
