# Signed-published result reconciliation — no inferred completion

Two historical `powerpc-control-v1` task records remained `claimed` even after the owner daemon published encrypted results. This is a **metadata discrepancy**, not a verified absence of execution. Replaying them can duplicate side effects.

`reconcile-signed-published-results.py` performs a read-only audit by default, using only the owning Unix user's database and result paths. It validates the expected X25519+Ed25519 identity fingerprint, verifies the identity signature, requires two byte-identical mirrored signed result envelopes bound to the exact runtime/task, checks a plausible publication timestamp, and validates the owner's private database integrity and mode.

With `--apply` and the **complete explicit set of currently claimed task IDs**, the script performs CAS-protected metadata classification:

`claimed → published_outcome_unverified`

It stores the existing signed-envelope file path but **does not fill in `completed_at`**, decrypt any private payload, mark execution success, register a new Ledger task, change queue data, or execute tools. Missing, invalid, mismatched or altered evidence fails closed. Re-running is a no-op only for records already classified; it cannot accept changed IDs or a nonprivate results directory.

The decrypted task outcome remains unknown when original private origin context cannot be recovered. A signed envelope demonstrates that the owned receiver signed and published some result, **not that the underlying objective succeeded**. The live daemon continues to suppress replay for all previously recorded task IDs.

No OpenAI platform hooks are involved; this changes owned task metadata only. Host-account path/UID are resolved locally rather than embedded in public source. The acceptance receipt remains private and includes SHA-256 hashes, classifications and remaining uncertainty without disclosing ciphertext.
