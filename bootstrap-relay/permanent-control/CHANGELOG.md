# Permanent Control Changelog

## 2026-10-04 — Continuity-Agent ledger session wiring

- The deployed Continuity-Agent delegation receiver now has a bounded candidate integration with the authoritative Concurrency Ledger session lifecycle.
- Before model admission or local-MCP execution, the receiver opens and heartbeats a dedicated role-free session as `actor:continuity-agent` through `concurrency-ledger-cagent-call`.
- Ledger session failure blocks delegation before model/tool work; regression coverage verifies ordering and fail-closed behavior.
- This transition grants no role assignment, project-read authority, task ownership, claim, run, lease, fencing, or mutation authority.
- Candidate source passed host compilation, receiver self-test, focused unit tests, and an exact-source live session-open/heartbeat probe.

## 2026-10-03

- Corrected fresh-origin identity and result URLs to the live `powerpc-control-v1` carrier paths. Marked the unauthenticated runtime-status endpoint as operator-only.
- Added redacted receipt summaries as the default publication mode. Full plaintext publication now requires an explicit `result_visibility: "public_plaintext"` request after review.
- Added focused tests for result redaction, explicit plaintext opt-in, and task binding.
- Replaced the current-tree plaintext health and directory-listing receipts with redacted summaries while preserving exact encrypted envelopes and hashes.
- Recorded the completed `list_dir` transport probe. Duplicate suppression and the remaining positive-acceptance steps are still pending.
