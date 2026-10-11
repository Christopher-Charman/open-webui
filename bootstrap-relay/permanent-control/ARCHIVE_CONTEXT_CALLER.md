# Owned historical context caller

The receiver now calls the existing owner-local `chatgpt-owned-context-reader` after the Ledger frontier and before either CLAIM path when the owner process sets `CAGENT_ARCHIVE_CONTEXT=1`. Default is OFF. Envelope fields cannot turn it on or redirect the reader.

The request is task-bound, read-only and limited to five records over 92 days, with a 12-second ceiling inside the existing wall/deadline budget. Receipts are bound to the request, task and window. The receiver validates historical-only authority flags, message provenance, byte limits and explicit index gaps, and rejects known credential patterns. This is not comprehensive secret detection or semantic contradiction resolution. Historical evidence can contain conflicting preferences; the origin must reconcile them against the current user request and current owner evidence. Old archives remain usable as dated history, with their gap disclosed.

When enabled, an unavailable or rejected reader blocks before any model or tool call only if the envelope explicitly declares context_requirement=historical. Independent authorized reads continue with UNAVAILABLE_NOT_REQUIRED. A historical dependency while the feature is disabled blocks before opening a coordination session. Optional retrieval consumes at most half the remaining budget. Existing completed receipts replay unchanged without new reads or effects. Rollback sets the flag to 0 for new tasks; task IDs remain immutable. Existing destination mutation denial remains unchanged.

The packet is returned in `historical_context` on the existing private delegation receipt to the originating reasoning process. It is deliberately excluded from the low-level CLAIM classifier and local MCP arguments. This is an owned receiver integration; it is not a native ChatGPT hook or automatic injection into every OpenWebUI chat.

## Acceptance

Local deterministic receiver tests: 27 passed, including enabled ordering, typed and untyped failures, exact replay, OFF baseline, negative provenance/privacy/binding cases and existing Ledger/destination admission tests. Live reader and host source checks are reported separately; source integration alone does not establish production activation. The flag must stay OFF until the real receiver canary has an accepted coordination session and owner readback. Track remaining live acceptance in repository-prime #89.

Host validation: all 27 receiver tests passed with Miniconda Python 3.12. The actual new caller function invoked the existing fixed runtime reader and validated five records, the history gap and historical-only state (Gateway job job_01M4MNR7FK000AHECZSE6Z3HM3). No model, Ledger session or local MCP calls were made by this read-only canary. Production enablement remains unverified.

Full staged receiver acceptance: Gateway job job_01M4MP7EYD00C3M679560JMEWN completed its real Ledger session/heartbeat/frontier, retrieved five records, dispatched runtime_health, and replayed identically. Three Ledger calls, one local MCP call, zero model calls, 2849 ms. No provider check suites or workflow runs were emitted for this PR as observed; the effective branch rules require a PR but no status check. Host tests are host tests, not GitHub CI. Production activation is recorded separately.

Live parity recovery: the installed receiver also contained an opt-in owned-objective assessment block absent from main. This block is retained verbatim in source, with a regression asserting that action completion cannot silently become objective completion. Deployment retains the existing pinned account identity via its owner-local launcher. Final receiver suite: 28 tests.
