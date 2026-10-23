# 2026-10-10 — Owned control daemon SQLite durability and effect admission

**Scope:** `fasthost.powerpc_darwin_org` GitHub-carried encrypted owner-controlled receiver. No OpenAI or provider safety subsystem changes.

## Incident
The managed host's control daemon was found **STOPPED** with stale heartbeat and historical `sqlite3.OperationalError: database is locked` failures in task-result publication. The exception handler attempted a second unguarded SQLite update, which could also raise and terminate the daemon. Public queue contained two previously expired tasks. Host-private durable database `PRAGMA quick_check=ok` had two older `claimed` records without `completed_at` or `result_path`; these cannot be presumed unexecuted or marked complete.

## Source change
- Bound all post-publication SQLite state updates behind a three-attempt rollback/retry helper. Transient locks resolve; persistent DB faults leave the already-claimed task `OUTCOME_UNRESOLVED` without executing the tool again.
- On claim insert/read DB failures, stop *before* any local MCP action.
- Keep an encrypted result publish exception from crashing the daemon when marking `publish_failed` also encounters a DB lock.
- Suspend `terminal_exec` through this encrypted queue until owner-bound task/run/lease/fencing and destination CAS authorization is actually implemented. A model-authored `bounded_operator` profile or platform provider transport is not write admission. Existing read-only capabilities remain subject to their original checks.
- Six new adversarial regressions; 34 source regression tests passed on the authenticated owner-controlled host.

## Deploy gate
Exact Git main source SHA and local host baseline must be reverified. Host script has pinned local UID and user identifiers that differ from portable Git source; deployment must **apply only the reviewed source delta** to the exact installed file and preserve those local bindings, existing keys, database, and published result contents. Back up exact predeploy bytes first. No unattended replay of old claimed tasks or effect-capable queue submissions.

Before daemon restart: inspect current queue, two unresolved claims, Git ruleset/provider restrictions, disable any effectful ingress in the exact deployed code, and check runtime concurrency. Only a read-only runtime-health canary and stable heartbeat may count as service recovery. No assertion of global ChatGPT/Codex/automation coordination.

**Separate unresolved:** protected `main` cannot serve as routine queue-write transport (GitHub active ruleset). Actions dispatch returned 422 despite repository `enabled=true`; this is an independent provider eligibility issue. Do not disable source protection or reroute a safety-denied operation.
