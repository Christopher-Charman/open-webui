# Owned runtime-control data branch — source transport separation

**Canonical source:** `Christopher-Charman/open-webui/main` through PR-gated, versioned merges.

**Operational data:** `refs/heads/runtime-queue-powerpc-darwin-org-v1` in the same user-owned GitHub repository, separately versioned. The active default-branch ruleset applies only to `~DEFAULT_BRANCH`; it must not be weakened to deliver routine encrypted commands.

The receiver now supports exactly two configured queue refs, legacy `main` for explicit backwards compatibility and `runtime-queue-powerpc-darwin-org-v1` as its default. It resolves the **selected branch** from the repository's Git advertisement and verifies an immutable commit SHA before reading `queue.json`; only fallback reads can use branch URLs. Arbitrary ref/URL inputs are rejected. Private keys and decryption context stay on the owner runtime.

The owned CLI `owned-queue-cas.py` only mutates `queue.json` on the exact operational branch using GitHub's current blob SHA, reads back the result, and never equates transport success with destination execution. Duplicate task envelopes remain idempotent, same-ID conflicts fail closed, expired/out-of-scope envelopes are rejected, and unknown delivery is not blindly retried. Retirement requires decrypting and verifying the signed encrypted result using the existing `origin-client.py` and owner-private context; it cannot accept a caller's unverified plaintext receipt.

**Default authority:** Read-only. The separate daemon-side `terminal_exec` denial remains active pending destination-specific claim/run/fence/CAS. Publishing an encrypted request does not create task or mutation authority.

**GitHub Actions:** No dependency for daemon-side polling or owner-authenticated CAS submission. GitHub Actions regression execution remains an independently tracked provider restriction (HTTP 422 despite repo enabled status); success of this route does not establish GitHub Actions recovery.

**Separate Evenio:** Evenio maintains `fasthost.evenio`, separate receiver, keys, state and business governance. This branch is exclusively for `powerpc-darwin.org` and cannot be reused for Evenio. No OpenAI-owned ChatGPT internals or native tool permissions are modified.

**Source tests:** Selected-branch immutable ref resolution, ambiguous ref rejection, strict allowed refs, SHA/CAS, idempotent replays, boundary/expiry/target rejection and safe result verification. **Live acceptance** still requires exact source deployment, owner identity and queue readback, signed/decrypted positive read-only result, durable replay, and safe CAS retirement; do not mark complete from source merge alone.
