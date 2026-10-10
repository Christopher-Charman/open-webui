# Continuity Agent destination-mutation admission (2026-10-10)

**Scope:** User-owned `delegate-cagent` receiver in the powerpc-darwin.org runtime, not OpenAI product infrastructure.

## Corrective change

The existing receiver opens a Ledger session, heartbeats, reads a project-scoped frontier and obtains a model/deterministic *task claim decision*. **None of those events is an authoritative destination write grant.** The accepted reader role is `LEDGER_PROJECT_READ`; no task/claim/run/lease/fence/version-CAS admission is established for a requested `terminal_exec` command.

`require_destination_effect_admission` now rejects every `terminal_exec` request as `destination_mutation_admission_unverified / BLOCKED` **before** Ledger session/open, model claim or local-MCP execution. Sender-provided authority hints, claims, fencing tokens, alleged global-idle flags or transport changes are never interpreted as permission. The receiver's independent `runtime_health`, `read_text` and `list_dir` paths remain admitted subject to the existing bounded checks.

This is deliberate *fail-closed mutation suspension on this receiver*, not removal of the underlying `terminal_exec` capability from other independently authorized operator surfaces. No deployed effectful caller may be classified protected merely because this particular one is gated.

## Residual work for safely re-enabling effectful delegation

Build an authenticated, owner-controlled destination admission interface that returns exact task/actor/role/destination/action/write-set and revision bound evidence; require current authorized Ledger task and run, atomic ownership/fence/lease or other project-specific equivalent, destination version-CAS preflight, idempotent dispatch and durable receipt/readback before permitting one action. Treat ambiguous delivery as unknown and reconcile before retry. Do not require universal ChatGPT-session visibility when resource-scoped fencing suffices; do not infer global idle from project-limited frontier counts. Distinct surfaces such as native Library writes and CLI changes require their own ingress controls.

Acceptance for this change is source and CI, then guarded deploy with exact live-host baseline byte hash and host-local objective completion overlay preservation, negative effectful canary (no Ledger or MCP call), positive independent read-only canary and host-private rollback.

This does not modify OpenAI IP, product safety settings, default ChatGPT inference or native tool-admission internals.
