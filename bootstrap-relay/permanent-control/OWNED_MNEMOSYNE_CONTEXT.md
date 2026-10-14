# Optional Mnemosyne context for Continuity Agent

This is an owned receiver integration, not a change to ChatGPT internals.
ChatGPT remains a connected external orchestration client. The owned
Continuity Agent retains its task/ledger/tool execution lifecycle.

Owner process setting CAGENT_MNEMOSYNE_CONTEXT=1 opts in. The envelope
cannot change this setting or route. Default OFF. The fixed read-only
local caller is webapp/runtime-domains/mnemosyne/context.py.

The added output is confined to the private durable delegation receipt.
It includes derived architecture memory with pinned Git provenance
labelled DERIVED_CONTEXT_ONLY; it is NOT sent to the CLAIM model, Ledger,
or local MCP arguments. Existing historical context, time budget,
destination admission, idempotent replay and mutating-tool authority are
unchanged. Failure of this optional source is recorded without blocking
an otherwise independently authorised read-only task.

There is no automatic memory injection into every OpenWebUI turn.
No new public listener, private transcript import, cross-machine sync,
or external embedding calls. Activation requires live host canary and
rollback verification; unit-test success alone does not justify enablement.
