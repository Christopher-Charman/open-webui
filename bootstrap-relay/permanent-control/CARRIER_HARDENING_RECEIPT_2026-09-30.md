# PowerPC control carrier hardening — source validation receipt — 2026-09-30

Status: SOURCE_VALIDATED / LIVE_DEPLOYMENT_PENDING

## Observed failure

The owned `powerpc-control-v1` receiver remained alive and continued publishing signed heartbeats while newly committed GitHub queue tasks were sometimes not observed for several minutes.

Current-session evidence:

- signed runtime identity and fingerprint verified for `fasthost.powerpc`;
- static identity/status mirrors returned HTTP 200;
- fresh-origin `runtime_health`, `read_text`, bounded `terminal_exec`, expiry and authority-attenuation tasks produced signed result envelopes;
- later queue tasks were immediately visible through the GitHub connector yet reached the receiver only after multi-minute delays;
- deployed daemon source SHA is `e369a367adde733a1ef60897561c893f43942ad0d50c747adea9cb67402ae954`;
- deployed source uses a mutable raw-GitHub `main` URL with a nanosecond query suffix and no-cache request headers;
- receiver logs contained no `queue_fetch_error=` records during the observed delays.

## Cache mechanism proven

External HTTP inspection of the raw GitHub queue path showed:

- `cache-control: max-age=300`;
- a plain request returned a cache MISS;
- an immediately following request with a unique query parameter returned a HIT for the same object, with the same ETag and GitHub request identity;
- a request carrying `Cache-Control: no-cache` and `Pragma: no-cache` also returned the cached object.

Therefore the previous nanosecond query suffix/no-cache headers do **not** bypass the mutable branch-path cache. The observed latency is consistent with the five-minute cache lifetime and is not evidence of HTTP fetch failures.

## Candidate change

The receiver keeps the same encrypted queue, task validation, local MCP execution, and result contract.

Queue acquisition becomes:

1. every 90 seconds, resolve `main` through the public GitHub `commits/main` API;
2. validate the returned 40-character commit SHA;
3. fetch `queue.json` from the immutable raw URL containing that SHA;
4. reuse that immutable SHA between ref checks;
5. if ref resolution fails or is rate-limited, clear the cached SHA and fall back to the existing mutable raw queue URL.

The `commits/main` API was independently observed with:

- `cache-control: public, max-age=60, s-maxage=60`;
- unauthenticated `x-ratelimit-limit: 60`;
- no 300-second `X-Poll-Interval` header in the observed response.

At a 90-second cadence this uses at most ~40 ref requests/hour before external/shared-IP effects and leaves nominal headroom.

The smaller Git-ref endpoint was rejected for this use because it explicitly advertised `X-Poll-Interval: 300`.

Environment overrides:

- `PPC_CONTROL_QUEUE_REF_URL`
- `PPC_CONTROL_QUEUE_SHA_URL_TEMPLATE`
- `PPC_CONTROL_QUEUE_REF_CHECK_SECONDS`

Minimum ref-check interval: 60 seconds; default: 90 seconds.

## Source validation

Latest GitHub Actions run: `36759721478`

Result: PASS

- Python syntax compilation: PASS
- commit-ref resolver present: PASS
- immutable-SHA raw queue path present: PASS
- mutable fallback present: PASS
- rate-limit diagnostics present: PASS
- nanosecond cache-buster absent: PASS
- forced no-cache headers absent: PASS

The temporary validation workflow was removed after validation.

## Live gate

Do not merge/deploy solely from this source receipt.

Required live acceptance:

1. verify `commits/main` and immutable raw-SHA queue access from `fasthost.powerpc`;
2. back up deployed receiver source;
3. install the exact reviewed candidate;
4. restart only the owned receiver;
5. verify signed heartbeat/fingerprint remains stable;
6. issue a fresh read-only `runtime_health` task;
7. verify signed result retrieval and decryption;
8. measure task pickup across at least one ref-check boundary;
9. verify API-rate-limit/fallback telemetry;
10. confirm local MCP/OpenWebUI sibling services remain healthy.

No new ingress, shell backend, credential, or authority surface is introduced.
