# PowerPC Owned Control Acceptance — 2026-10-01

Status: **ACCEPTED**

Promotion:
- `PERMANENT_ACCESS=ACCEPTED`
- `POWERPC_OWNED_CONTROL_ACCEPTANCE=PASS`

Scope: the product-independent owned control path for `fasthost.powerpc`. This does **not** imply Gateway SSH acceptance, ChatGPT Secure-MCP tool projection, or C-Agent/inter-agent control-plane acceptance.

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

## Boundary after promotion

This acceptance closes the repeated human-as-transport / session-bound control gap for bounded PowerPC operations.

Still separate:
- `INTER_AGENT_CONTROL_PLANE=NOT_YET_ACCEPTED` until a delegated C-Agent receipt chain passes.
- Gateway/Tailscale/management-SSHD remains its own ingress branch.
- Secure MCP host connection remains distinct from ChatGPT product/tool projection.
- aggregate platform health (for example Ollama health) is not the same condition as control-transport acceptance.
