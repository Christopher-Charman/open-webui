# Local MCP source validation receipt — 2026-09-30

**Scope:** source-only candidate validation  
**Branch:** `tooling/local-mcp-dependency-decoupling`  
**Live deployment:** NOT PERFORMED  
**Admission:** NOT AUTHORISED

## Environment

- Validation runtime: Node `v22.16.0`
- npm available: `10.9.2`
- Target runtime family: Node 22 / EL7-compatible host build

## Passed

- `path-policy.mjs` syntax: PASS
- `path-policy.test.mjs` syntax: PASS
- in-root existing file resolution: PASS
- `..` traversal rejection: PASS
- absolute outside-root rejection: PASS
- in-root symlink resolving outside root rejection: PASS

Observed marker:

`PATH_POLICY=PASS`

## Static hardening review

Candidate source now:

- uses package-local MCP SDK/Zod imports rather than Desktop Commander private dependencies;
- normalises and realpath-checks file/directory targets;
- reads at most the requested `max_bytes` instead of loading a whole file;
- limits directory enumeration to 500 entries;
- caps health-check output;
- applies a 30-second health-check timeout;
- retains bounded terminal execution timeout/output controls;
- handles process spawn errors.

## Not yet proven

This source receipt does **not** establish:

- installability on the Fasthosts Node 22 EL7 runtime;
- generated local package-lock correctness;
- deployed source parity;
- local MCP protocol discovery against the pinned dependencies;
- positive execution of all four tools;
- negative bounds through the live MCP interface;
- interaction with the Secure MCP tunnel;
- absence of regressions in Open Terminal or other services.

Those remain mandatory before merge/deployment/admission.


## Reproducible dependency validation

Temporary branch-only GitHub Actions run: `36730891204`

Result: **PASS**

Completed under Node 22:

- generated `package-lock.json`;
- `npm ci --ignore-scripts --no-audit --no-fund`;
- source syntax checks;
- `PATH_POLICY=PASS`;
- committed only the generated lockfile.

Generated lock commit:

`8764d4c04f0af13484ab93e1d5231130acab8869`

Lockfile blob:

`b18ff9bcb6bc2e020372c3fd73d211a23420c735`

Verified direct packages:

- `@modelcontextprotocol/sdk 1.31.0`
- `zod 3.25.76`

The temporary workflow was removed in commit:

`8f24ff3862e98aeda74cb249c438e3302c047d2d`

No CI scaffolding is intended to merge with the candidate.
