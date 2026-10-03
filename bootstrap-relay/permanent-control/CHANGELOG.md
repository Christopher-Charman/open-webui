# Permanent Control Changelog

## 2026-10-03

- Corrected fresh-origin identity and result URLs to the live `powerpc-control-v1` carrier paths. Marked the unauthenticated runtime-status endpoint as operator-only.
- Added redacted receipt summaries as the default publication mode. Full plaintext publication now requires an explicit `result_visibility: "public_plaintext"` request after review.
- Added focused tests for result redaction, explicit plaintext opt-in, and task binding.
- Replaced the current-tree plaintext health and directory-listing receipts with redacted summaries while preserving exact encrypted envelopes and hashes.
- Recorded the completed `list_dir` transport probe. Duplicate suppression and the remaining positive-acceptance steps are still pending.
