# Permanent Control Changelog

## 2026-10-05 — Continuity-Agent admission determinism accepted live

- Fixed nondeterministic CLAIM/DECLINE inference by adding explicit Ollama seed `42` to the existing admission request; prompt, model, temperature, context/output limits and authority/capability policy are unchanged.
- Source PR #12 merged at `e4668f36f6cf8b057c9df22aa3116c57e7605d21`; seeded receiver blob `d6c140d9a9c840090748a9ddd2e6ca7cc74defac` was installed byte-for-byte and self-tested.
- Before fix, six identical unseeded requests produced 5 CLAIM / 1 DECLINE; after fix, six identical live receiver admissions produced 6 CLAIM / 0 DECLINE.
- Fresh full delegation `cagent-seed-e2e-20261005T035941` completed session -> heartbeat -> frontier -> seeded model -> local MCP with 3 ledger calls, 1 model call and 1 local-MCP call.
- Identical-envelope replay returned the same durable receipt without re-execution; legacy `cagent-status` acceptance fingerprint remains `sha256:ee13430462886036621107f85c95fd4a9d2b76066a2e9d26ae2a17b8a1ea604f`.
- No TASK_OWNER, task-claim, run, lease, fencing or destination-mutation authority was added.
- Receipt: `C_AGENT_ADMISSION_DETERMINISM_ACCEPTANCE_20261005.json`.


## 2026-10-04 — Continuity-Agent project-frontier consumption accepted live

- Promoted automatic `concurrency.orchestration` frontier consumption to live accepted at the pre-model boundary.
- Installed exact merged receiver/verifier source from `197277c6049c9fe217fc1ba45a954018f472864b`; receiver self-test and legacy `cagent-status` fingerprint both remained PASS.
- Fresh live receipts proved session open -> heartbeat -> `ledger_frontier_get` -> model admission with exactly three ledger calls and one frontier digest.
- The final acceptance receipt was deliberately BLOCKED after the existing model returned `DECLINE`; no local-MCP action was bypassed or forced.
- Identical blocked replay returned the same durable receipt without another ledger/model execution.
- Live read-back confirmed the project-reader assignment remains ACTIVE and the Continuity-Agent still has no task-ownership rows.
- The exact claim input subsequently returned `CLAIM` in isolation; claim-decision reproducibility is recorded as a separate unresolved admission-quality issue, not a frontier defect.
- Receipt: `C_AGENT_FRONTIER_CONSUMPTION_ACCEPTANCE_20261004.json`.

## 2026-10-04 — Continuity-Agent automatic project-frontier consumption implemented

- Added the already-authorized `concurrency.orchestration` project-reader assignment to the receiver's ledger request binding.
- Receiver order is now session open -> heartbeat -> bounded `ledger_frontier_get` -> model admission -> local-MCP execution.
- The frontier must retain `SUMMARY_IS_NOT_AUTHORITY` and `READY_UNCLAIMED_IS_NOT_CLAIM_ADMISSION`; only its SHA-256 is added to delegation evidence.
- Frontier data is not passed to the claim model and cannot create TASK_OWNER/claim/run/lease/fencing/destination-mutation authority.
- Added fail-closed frontier regression coverage and opt-in `--require-ledger-frontier` acceptance verification while preserving the legacy acceptance fingerprint.
- Live acceptance remains pending until merged source is installed and exercised.

## 2026-10-04 — Continuity-Agent ledger session live acceptance

- Promoted the receiver's role-free Concurrency Ledger session open/heartbeat integration from implementation-pending to live accepted.
- Installed the exact current receiver source with the supported Python 3.12 shebang and verified its SHA-256.
- Six focused regression tests passed; a fresh read-only live delegation recorded ledger session + heartbeat evidence before claim/local-MCP execution.
- Identical envelope replay returned the existing durable receipt without re-execution.
- The returned session was independently read back from the live ledger as `actor:continuity-agent` / `openwebui:continuity-agent`, active, heartbeat persisted, with no role assignment.
- Added opt-in ledger-aware verification (`--require-ledger-session`) that requires session + heartbeat evidence and `ledger_calls=2`, while preserving the 1 October verifier output/fingerprint in default mode; role/project/task/run/lease authority remains explicitly ungranted.

## 2026-10-04 — Continuity-Agent executable entrypoint

- Corrected the host-specific receiver shebang from `/usr/bin/env python3` (which resolves to Python 3.6.8 on the Fasthosts gateway) to the verified webapp Python 3.12 runtime.
- Added regression coverage so the deployed executable cannot silently regress to an unsupported interpreter.

## 2026-10-04 — Continuity-Agent ledger session wiring

- The Continuity-Agent delegation receiver candidate now has a bounded integration with the authoritative Concurrency Ledger session lifecycle; live receiver deployment is a separate acceptance step.
- Before model admission or local-MCP execution, the receiver opens and heartbeats a dedicated role-free session as `actor:continuity-agent` through `concurrency-ledger-cagent-call`.
- Ledger session failure blocks delegation before model/tool work; regression coverage verifies ordering and fail-closed behavior.
- Receiver model resolution is decoupled from the mutable OpenWebUI `continuity-agent` preset; the accepted receiver claim model remains `qwen2.5-coder:1.5b-instruct-q4_K_M` and is checked against live Ollama availability.
- This transition grants no role assignment, project-read authority, task ownership, claim, run, lease, fencing, or mutation authority.
- Candidate source passed host compilation, receiver self-test, focused unit tests, and an exact-source live session-open/heartbeat probe.

## 2026-10-03

- Corrected fresh-origin identity and result URLs to the live `powerpc-control-v1` carrier paths. Marked the unauthenticated runtime-status endpoint as operator-only.
- Added redacted receipt summaries as the default publication mode. Full plaintext publication now requires an explicit `result_visibility: "public_plaintext"` request after review.
- Added focused tests for result redaction, explicit plaintext opt-in, and task binding.
- Replaced the current-tree plaintext health and directory-listing receipts with redacted summaries while preserving exact encrypted envelopes and hashes.
- Recorded the completed `list_dir` transport probe. Duplicate suppression and the remaining positive-acceptance steps are still pending.
