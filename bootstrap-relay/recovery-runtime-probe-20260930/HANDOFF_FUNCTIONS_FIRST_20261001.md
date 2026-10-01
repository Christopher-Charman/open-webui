# OpenWebUI Recovery Handoff — Functions-First Boundary — 2026-10-01

Status: HANDOFF_REQUIRED / SHARED_CONTROL_QUEUE_OWNED_BY_PERMANENT_CONTROL_ACCEPTANCE

Role/lane:
- role: ChatGPT iOS chat assistant session
- lane: OpenWebUI functional recovery
- runtime: fasthost.powerpc
- project: hosting.fasthosts.webapp

## Why handoff now

The permanent-control lane is actively cycling acceptance tests on the shared encrypted PowerPC queue.

Observed sequence during this recovery turn:
- ppc-accept-list-1790815585
- ppc-accept-read-1790815634-15100
- ppc-accept-expired-1790815688-21510
- ppc-accept-authority-1790815766-18357
- current owner at handoff:
  ppc-accept-failclosed-1790815846-21962

The OpenWebUI recovery append correctly failed closed when main/queue changed during compare-and-swap.

Do not compete with this sequence.

## Current deterministic live recovery state

Verified/decrypted compact snapshot:
task: owui-recovery-compact-1790815401

Ollama:
- HEALTHY
- process running
- 127.0.0.1:11434 open
- /api/version = 200
- /api/tags = 200
- configured OpenWebUI endpoint matches http://127.0.0.1:11434
- 15 models present
- launcher candidate: /home/storage/781/4477781/user/webapp/run-ollama.sh
- binary: /home/storage/781/4477781/user/webapp/miniconda/bin/ollama

Local Agent:
- exactly one active row
- id: local-agent-mini-c-agent
- name: Local Agent (Mini C-Agent)
- base_model_id: qwen2.5-coder:1.5b-instruct-q4_K_M
- deterministic plan: NOOP
- DO NOT rebind, pull a model, recreate preset, or use Granite

Frontend:
- stock loader.js = 0 bytes
- stock custom.css = 0 bytes
- accepted postmount marker present
- semantic binder v2 marker present
- v20260930.4 regressed hero marker present
- state: POSTMOUNT_REGRESSED_HERO_PRESENT

Voice:
- warmSelectedVoice absent
- /api/v1/audio/local-voice/warm absent
- playback primitives present
- Cortana literal present
- ready literal present
- state: PLAYBACK_PRIMITIVE_PRESENT
- audible READY candidate = true

## Functions-first substrate now implemented

Branch:
recovery/openwebui-readonly-probe-20260930

Core:
- recovery_functions.py
- test_recovery_functions.py
- collect_ollama_evidence.py
- collect_local_agent_binding.py
- collect_frontend_voice_evidence.py
- snapshot_recovery_state.py
- test_snapshot_recovery_state.py
- compact_recovery_snapshot.py
- test_compact_recovery_snapshot.py
- validate_qwen_inference.py
- locate_voice_trigger.py

Important commits:
- classifiers: 06221b9f8236afcc0f4ff59464455968cde8d8f7
- classifier tests: bb42f68054586b90674e5b5fc7f86ce54da11f4f
- callable Ollama collector: c902458c624e684abf62d2775c871a3a1c766ef2
- callable binding collector: c8c3e6cb053fefac5320e06b4af3a53ac9f48bb7
- configured Ollama URL collection: c537d98a6a52095c8a489e0055e2c61bc9049443
- frontend/voice collector: 68e42d333b45102b70cb1a8784695dd302bc9a17
- composed snapshot: c930635491df4a85bbeb9979977aca3ac9dbc2fe
- snapshot tests: b86beb72a27d877b93e1c5a126e2b1dd5c8ed0d8
- compact snapshot: 09b21c1d50ab9f419e461539a27d5838fa4e859c
- compact snapshot test: 859759c12d024d40b0ad624169fd6c2faf0ef02c
- Qwen validator: 03c1cf194ca8a3d44550686fe7e88cb11d9deeb3
- compact voice locator: df8e429e003b30bacb460f25ae48f648ffbba802
- functions-first checkpoint: eb94af02457a5c4ca8b49fa2627945c3e1b5eb2a

## Prepared but NOT queued

A single bounded validation envelope was prepared for:
- direct Qwen inference:
  exact model qwen2.5-coder:1.5b-instruct-q4_K_M
  sentinel QWEN_LOCAL_AGENT_OK
- compact voice trigger localization

Task id prepared in this session:
owui-frontier-validate-1790815726

It was NOT appended because the queue moved during the atomic compare-and-swap check.

Do not reuse this envelope after its TTL. Generate a fresh one when the shared queue is actually free.

## Next safe sequence

1. refresh open-webui/main and queue.json;
2. verify permanent-control acceptance sequence has stopped;
3. verify no newer live queue owner;
4. generate a fresh envelope using current signed runtime identity;
5. run in one bounded terminal_exec:
   - validate_qwen_inference.py
   - compact locate_voice_trigger.py
6. verify/decrypt receipt;
7. if Qwen PASS:
   backend/model recovery is accepted;
8. use exact voice file/line indices to remove only unsolicited startup READY playback;
9. preserve 1.3.4-nowarm and silent cache behavior;
10. then repair presentation:
    - demote/remove v20260930.4 fixed-body hero presenter;
    - restore explicit landing-vs-chat ownership from accepted v1.4.5 lineage;
    - preserve zero-byte stock loader/custom.css;
11. device validate fresh launch, Majel/Kokoro, active chat, landing page, sidebar, Continuity controls.

## Hard prohibitions

Do not:
- use Granite for Local Agent;
- rebind Local Agent while current Qwen binding remains correct;
- pull models unnecessarily;
- restart healthy Ollama;
- recreate the Local Agent preset;
- reintroduce audible warmup;
- mutate stock loader.js/custom.css;
- broad-revert concurrent permanent-control commits;
- append recovery tasks while the acceptance lane owns the shared queue.
