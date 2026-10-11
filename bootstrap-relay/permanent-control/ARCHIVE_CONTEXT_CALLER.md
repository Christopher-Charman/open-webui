# Owned historical context caller

The receiver now calls the existing owner-local `chatgpt-owned-context-reader` after the Ledger frontier and before either CLAIM path when the owner process sets `CAGENT_ARCHIVE_CONTEXT=1`. Default is OFF. Envelope fields cannot turn it on or redirect the reader.

The request is task-bound, read-only and limited to five records over 92 days, with a 12-second ceiling inside the existing wall/deadline budget. Receipts are bound to the request, task and window. The receiver validates historical-only authority flags, message provenance, byte limits and explicit index gaps, and rejects known credential patterns. This is not comprehensive secret detection or semantic contradiction resolution. Historical evidence can contain conflicting preferences; the origin must reconcile them against the current user request and current owner evidence. Old archives remain usable as dated history, with their gap disclosed.

When enabled, an unavailable or rejected reader blocks before any model or tool call. Existing completed receipts replay unchanged without new reads or effects. Rollback sets the flag to 0 for new tasks; task IDs remain immutable. Existing destination mutation denial remains unchanged.

The packet is returned in `historical_context` on the existing private delegation receipt to the originating reasoning process. It is deliberately excluded from the low-level CLAIM classifier and local MCP arguments. This is an owned receiver integration; it is not a native ChatGPT hook or automatic injection into every OpenWebUI chat.

## Acceptance

Local deterministic receiver tests: 25 passed, including enabled ordering, typed and untyped failures, exact replay, OFF baseline, negative provenance/privacy/binding cases and existing Ledger/destination admission tests. Live reader and host source checks are reported separately; source integration alone does not establish production activation. The flag must stay OFF until the real receiver canary has an accepted coordination session and owner readback. Track remaining live acceptance in repository-prime #89.

Host validation: all 25 receiver tests passed with Miniconda Python 3.12. The actual new caller function invoked the existing fixed runtime reader and validated five records, the history gap and historical-only state (Gateway job job_01M4MNR7FK000AHECZSE6Z3HM3). No model, Ledger session or local MCP calls were made by this read-only canary. Production enablement remains unverified.
