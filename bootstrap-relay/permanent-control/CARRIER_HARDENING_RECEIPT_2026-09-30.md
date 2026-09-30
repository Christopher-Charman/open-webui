# PowerPC control carrier hardening — source validation receipt — 2026-09-30

Status: SOURCE_VALIDATED / LIVE_DEPLOYMENT_PENDING

## Observed failure

The owned `powerpc-control-v1` receiver remained alive and continued publishing signed heartbeats while fresh GitHub queue tasks intermittently stopped producing results.

Current-session evidence:

- signed runtime identity and fingerprint verified for `fasthost.powerpc`;
- static identity/status mirrors returned HTTP 200;
- fresh-origin `runtime_health`, `read_text`, bounded `terminal_exec`, expiry and authority-attenuation tasks produced signed result envelopes;
- later queue tasks remained visible through raw GitHub but were temporarily unclaimed while receiver heartbeats continued;
- deployed source family polls every 7 seconds and the repository source forced a unique `?t=<time_ns>` raw-GitHub URL plus no-cache headers.

## Candidate change

`daemon.py` retains the same encrypted queue/task semantics but:

- uses a 30-second cache-buster bucket by default instead of a unique nanosecond URL per poll;
- removes forced no-cache request headers;
- records HTTP status for `HTTPError`;
- records reason class for `URLError`.

Environment override:

`PPC_CONTROL_QUEUE_REFRESH_BUCKET_SECONDS`

Minimum accepted value: 10 seconds.

## Source validation

GitHub Actions run: `36758411580`

Result: PASS

- Python syntax compilation: PASS
- bounded refresh setting present: PASS
- nanosecond cache-buster absent: PASS
- forced no-cache headers absent: PASS
- HTTP/URL error diagnostic markers present: PASS

The temporary validation workflow was removed after validation.

## Live gate

Do not merge/deploy solely from this source receipt.

Required live acceptance:

1. obtain bounded operator execution through the already-owned receiver or independently authorised managed-runtime route;
2. back up deployed receiver source;
3. install the exact candidate commit;
4. restart only the owned receiver;
5. verify signed heartbeat/fingerprint remains stable;
6. issue a fresh read-only `runtime_health` task;
7. verify signed result retrieval and decryption;
8. confirm repeated queue polls do not regress result delivery;
9. confirm local MCP/OpenWebUI sibling services remain healthy.

No new ingress, shell backend or authentication mechanism is introduced.
