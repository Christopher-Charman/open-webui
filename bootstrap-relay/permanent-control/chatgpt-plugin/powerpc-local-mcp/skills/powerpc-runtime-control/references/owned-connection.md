# Owned connection and execution

## Verified binding

- Canonical runtime: `fasthost.powerpc_darwin_org`; wire protocol `powerpc-control-v1`, version 1, retains legacy target `fasthost.powerpc`.
- Repository: `Christopher-Charman/open-webui`, branch `main`.
- Transport source directory: `bootstrap-relay/permanent-control/`.
- Queue: `bootstrap-relay/permanent-control/queue.json`.
- Fresh identity: `https://www.powerpc-darwin.org/static/powerpc-control-v1/identity.json`.
- Encrypted result: `https://www.powerpc-darwin.org/static/powerpc-control-v1/results/<task_id>.json`.
- Verified key fingerprint: `SHA256:l7SrivQiY5uhxagCB/L9SR7IvXH3EKcP33HdEgeBaRI`.
- Executor: UID `2257347`, user `csh3280350`, host `hp3-rr-1024747.hostingp3.local`.
- Namespace: `/home/storage/781/4477781/user`.
- Local MCP: `/home/storage/781/4477781/user/webapp/bin/local-mcp`.

The receiver polls GitHub and invokes the existing local MCP. The iOS device needs no daemon or local software: execution occurs in ChatGPT's available execution surface and on the managed runtime. This requires an authenticated GitHub connection with repository write tools exposed in the conversation. Do not promise that an arbitrary iOS chat exposes those tools. A saved plugin release and a successful tool call are separate evidence.

## Preferred: encrypted direct-origin route

Use this route for sensitive arguments or results and for ordinary work when Python, cryptography and HTTPS are available. It does not require GitHub Actions, Desktop Commander, a paid relay, a new API subscription, or an iOS-side process.

1. Retrieve `bootstrap-relay/permanent-control/origin-client.py` from the repository using GitHub. Reviewed blob at acceptance: `b7b370cf68473448f7c3f94a8adb3b90494a9f43`. Review material source changes before execution; never execute an unrelated similarly named script.
2. Fetch the current identity JSON via HTTPS. Use Python 3 with `cryptography`. Check the signed identity and pin the fingerprint below. If keys changed, recover authenticated key-rotation evidence; never silently accept a new self-signed key.
3. Create a unique task ID and prepare the task in private scratch space. Example (substitute unique ID and paths):

```sh
python origin-client.py prepare \
  --identity identity.json \
  --expected-fingerprint SHA256:l7SrivQiY5uhxagCB/L9SR7IvXH3EKcP33HdEgeBaRI \
  --tool runtime_health --arguments '{}' --authority read_only \
  --ttl 600 --task-id UNIQUE_TASK_ID \
  --output envelope.json --context private-context.json
```

4. Fetch the current queue and blob SHA. Preserve the entire queue and every unrelated task. Append only the encrypted envelope to its `tasks` array using GitHub's conditional file update with that SHA. On conflict, fetch and merge again. Respect the receiver's queue limit; do not delete other sessions' tasks to make room.
5. Poll the unique encrypted result URL, allowing receiver latency. Use bounded waits and keep the user informed. Never resubmit a possibly executed mutation with a new ID merely because its response is delayed.
6. Decode with the same private context:

```sh
python origin-client.py decode --result result.json \
  --context private-context.json --output receipt.json
```

7. Check verified task ID, executor UID/user, namespace/local-MCP path, completion state, inner tool error and actual output. A transport pass is not a service-health pass. Persist only the minimal non-secret evidence needed.
8. Fetch the queue again, remove only this completed task, and update using the fresh SHA. Preserve concurrent additions. Delete this task's private context after verification and necessary recovery handling; never commit it, display its shared secret, or persist it in general-purpose memory.

Use `read_only` for inspection. `terminal_exec` requires `bounded_operator` and an explicitly authorized, narrowly scoped command; this is not blanket permission to mutate. Inspect the tool schema/current implementation before constructing unfamiliar arguments.

## Connector-only alternative: public-safe Actions adapter

If the session has GitHub connector tools but lacks local crypto/HTTPS execution, the existing adapter can perform non-sensitive checks:

- Request: `bootstrap-relay/permanent-control/chatgpt-request.json`.
- Workflow: `.github/workflows/chatgpt-owned-control-request.yml`.
- Result: `bootstrap-relay/permanent-control/chatgpt-results/<request_id>.json`.

This repository is PUBLIC. The request and decrypted result are committed as plaintext. Never use this adapter for credentials, private file contents, personal data, sensitive logs or secret-bearing commands. If privacy cannot be established, stop before publishing and use the encrypted route or an already authenticated native connection.

Fetch the current request and ensure its matching result exists before replacing it. Serialize requests; do not overwrite another session's pending work. Use the current blob SHA for the update. A public-safe health request is:

```json
{
  "schema": "chatgpt-owned-control-request-v1",
  "request_id": "UNIQUE_REQUEST_ID",
  "target_runtime_id": "fasthost.powerpc_darwin_org",
  "tool": "runtime_health",
  "arguments": {},
  "authority_ceiling": "read_only",
  "ttl": 300
}
```

Check the current adapter's accepted schema before sending; preserve required fields. Fetch the unique result and validate its request ID, identity fingerprint, executor, namespace, completion state and inner result. GitHub Actions job success alone is insufficient. Use `actions/runs?head_sha=<request commit>` if workflow status is needed; an unsupported connector URL is not evidence that the workflow is absent.

## Optional native Secure MCP Tunnel

Persisted alias `powerpc-local-mcp`, historical tunnel ID `tunnel_6abbc4d379dc8191aadb51eb636d454f`. Treat these as historical routing data, not fresh connectivity evidence. Use only a supported authenticated ChatGPT tunnel binding if exposed. Do not convert the tunnel ID into an invented `https://api.openai.com/v1/mcp/...` URL. Empty package MCP declarations do not invalidate the owned route.

## Acceptance evidence, 2026-10-02 UTC

- From this ChatGPT conversation: public-safe health request `cg-20261002-ios-health-2ab5a3ec`, request commit `ee5295b414d1966fff7d80274f9444d26fecfd7a`; verified receipt reached UID 2257347 and the correct local MCP.
- Health transport passed; runtime health reported terminal gateway failure while OpenWebUI, broker, Kokoro, Pocket, Open Terminal and Ollama passed. Treat this as a dated snapshot.
- Independent encrypted direct-origin `list_dir` task `ios-private-check-2ab5a3ec` completed; signature/decryption and executor binding passed. Submission `d511961fc2dd65a160f0cedbec0029c6c7edc737`; completed task removed in `923be472deccab6c8c404061d3d8e6c65446a2dc`.
- No Desktop Commander or paid relay was used for either verification. Exact iOS UI availability was not tested; do not claim otherwise.
