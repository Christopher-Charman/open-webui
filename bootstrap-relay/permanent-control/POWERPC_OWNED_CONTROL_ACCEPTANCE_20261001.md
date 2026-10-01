# PowerPC Owned Control Acceptance — 2026-10-01

Status: **ACCEPTED**

Promotion:
- `PERMANENT_ACCESS=ACCEPTED`
- `POWERPC_OWNED_CONTROL_ACCEPTANCE=PASS`
- `INTER_AGENT_CONTROL_PLANE=ACCEPTED`

Scope: the product-independent owned control path for `fasthost.powerpc`, including the accepted bounded Continuity Agent delegation chain. This does **not** imply Gateway SSH acceptance or ChatGPT Secure-MCP product/tool projection.

## Runtime binding

- runtime: `fasthost.powerpc`
- user: `csh3280350`
- UID: `2257347`
- hostname: `hp3-rr-1024747.hostingp3.local`
- webapp: `/home/storage/781/4477781/user/webapp`
- bounded local MCP tools: `runtime_health`, `read_text`, `list_dir`, `terminal_exec`

## Root cause closed

The receiver's fast queue path used the branch alias at `raw.githubusercontent.com`. Direct host evidence showed repeated 7-second polling while a newly committed acceptance task was never observed. The raw endpoint reported `X-Cache: HIT`; the task was absent from both SQLite and daemon logs.

Repair:
- `5b78433f88fd286a4712670d3c0d19789de70bb8` — add a bounded GitHub Contents API fallback every 75 seconds while retaining fast raw polling.
- `d0566fe455113a87065c0602974240ece5293a0b` — add deterministic `powerpc-control diagnose <task_id>` classification.
- `f0ce079cd3dae0e7aea42505cabf5e37a60305d9` — pin the installer to the repaired receiver build.

Live proof after deployment:
- stale branch detected: `queue_branch_stale raw_sha=... api_sha=...`
- the concurrent task `owui-recovery-compact-1790815401` was then admitted and completed.
- strict acceptance tasks subsequently traversed the same fallback path successfully.

## Strict acceptance

GitHub Actions:
- workflow: `Accept PowerPC Permanent Control`
- run: `36795401387`
- attempt: `2`
- conclusion: `success`
- completed: `2026-10-01T00:53:44Z`

Machine markers:

```text
IDENTITY_SIGNATURE_AND_PIN=PASS
FRESH_ORIGIN_LIST_DIR=PASS
DUPLICATE_SUPPRESSION=PASS
FRESH_ORIGIN_READ_TEXT=PASS
EXPIRY_ENFORCEMENT=PASS
AUTHORITY_ATTENUATION=PASS
FAIL_CLOSED_WRONG_RUNTIME_NO_RECEIPT=PASS
FRESH_ORIGIN_TERMINAL_EXEC=PASS
FAIL_CLOSED_SIDE_EFFECTS=PASS
FAIL_CLOSED_UNKNOWN_CAPABILITY=PASS
POST_ACCEPTANCE_HEARTBEAT=PASS
FRESH_SESSION_CALLABILITY=PASS
BROWSER_COOKIE_INDEPENDENCE=PASS
TEMPORARY_TOKEN_INDEPENDENCE=PASS
DESKTOP_COMMANDER_QUOTA_INDEPENDENCE=PASS
OPENAI_PRODUCT_BINDING_INDEPENDENCE=PASS
ORIGIN_RETRIEVAL=PASS
POWERPC_OWNED_CONTROL_ACCEPTANCE=PASS
```

Conflict-safe cleanup retired only the acceptance run's own task IDs; concurrent queue entries were preserved.

## Continuity Agent delegation acceptance

The bounded inter-agent chain is also accepted:

```text
ChatGPT origin
→ encrypted PowerPC control ingress
→ continuity-agent delegation adapter
→ model-mediated CLAIM
→ bounded local MCP action
→ durable nested receipt
→ signed/encrypted outer result
```

Accepted evidence:
- first outer task: `ppc-cagent-e2e-3d7ddcea537e4b50a346` — `COMPLETED`
- retry outer task: `ppc-cagent-retry-cc12ef294e924e4a899f` — `COMPLETED`
- nested task: `cagent-e2e-9e98f0faf16d4c6f80dd` — `COMPLETED`
- agent: `continuity-agent`
- model: `qwen2.5-coder:1.5b-instruct-q4_K_M`
- model calls: `1`
- local-MCP calls: `1`
- retry without nested re-execution: `PASS`
- evidence fingerprint: `sha256:ee13430462886036621107f85c95fd4a9d2b76066a2e9d26ae2a17b8a1ea604f`

Durable machine surfaces:
- `CONTINUITY_AGENT_DELEGATION_ACCEPTANCE_20261001.json`
- `verify-continuity-delegation.py`
- `powerpc-control cagent-status`
- `powerpc-control cagent-watch`

The status command recomputes the live evidence and compares it with the checkpoint fingerprint. It fails closed on drift rather than silently preserving an accepted label. The existing cron-driven `powerpc-control ensure` path runs the watcher at a bounded interval (default 300 seconds); it records only state transitions and does not auto-repair ambiguous evidence drift.

Automation commits:
- `de39e6f125ce84c006528ad3c2c22a342472ad0f` — deterministic acceptance verifier.
- `da454445db2b3706299b435a82419ac84495ccd7` — durable machine-readable acceptance checkpoint.
- `9a443cf5ca29c2d4272cc63f501435c0e3685f91` — machine-verifiable `cagent-status`.
- `3cfb96399fa6bc6ee29f137672d4356c1f373425` — bounded transition-only drift watcher.
- `94f898abd9563be12b3ad70a276a60e80647225e` — installer pin advanced to the watcher build.

## Boundary after promotion

This acceptance closes the repeated human-as-transport / session-bound control gap for bounded PowerPC operations.

Still separate:
- Gateway/Tailscale/management-SSHD remains its own ingress branch.
- Secure MCP host connection remains distinct from ChatGPT product/tool projection.
- aggregate platform health (for example Ollama health) is not the same condition as control-transport acceptance.
