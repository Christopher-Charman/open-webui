# Permanent Control Changelog

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
