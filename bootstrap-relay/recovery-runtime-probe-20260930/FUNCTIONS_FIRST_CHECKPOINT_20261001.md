# OpenWebUI Recovery Functions-First Checkpoint — 2026-10-01

Status: LIVE_SNAPSHOT_PASS / QWEN_BOUND / FRONTEND_REGRESSION_CONFIRMED / VOICE_TRIGGER_CANDIDATE / SHARED_QUEUE_BUSY

## Live deterministic snapshot

Task:
`owui-recovery-compact-1790815401`

Receipt:
- signature verification: PASS
- decryption: PASS
- completion_state: COMPLETED
- executor: `fasthost.powerpc`
- uid: `2257347`
- user: `csh3280350`

Classifier result:

### Ollama
- state: `HEALTHY`
- port 11434: OPEN
- process: RUNNING
- `/api/version`: 200
- `/api/tags`: 200
- configured endpoint matches `http://127.0.0.1:11434`
- model count: 15
- canonical launcher candidate:
  `/home/storage/781/4477781/user/webapp/run-ollama.sh`
- Ollama binary:
  `/home/storage/781/4477781/user/webapp/miniconda/bin/ollama`

### Local Agent
Exactly one workspace row:
- id: `local-agent-mini-c-agent`
- name: `Local Agent (Mini C-Agent)`
- active: true
- base_model_id: `qwen2.5-coder:1.5b-instruct-q4_K_M`

Decision:
- state: `NOOP`
- target already correct
- no Granite binding remains on Local Agent
- no model pull, DB mutation, preset recreation, or restart justified

### Frontend
- stock `loader.js`: 0 bytes
- stock `custom.css`: 0 bytes
- accepted postmount marker: present
- semantic binder v2 marker: present
- regressed hero presenter v20260930.4 marker: present
- deterministic classification:
  `POSTMOUNT_REGRESSED_HERO_PRESENT`

### Voice
- old warm helper: absent
- old warm endpoint: absent
- playback primitives: present
- Cortana literal: present
- READY literal: present
- deterministic classification:
  `PLAYBACK_PRIMITIVE_PRESENT`
- audible READY candidate: true

Therefore the startup speech regression is downstream playback logic, not the removed cache-warming path.

## Functions-first recovery substrate

Isolated branch:
`recovery/openwebui-readonly-probe-20260930`

Implemented:
- `recovery_functions.py`
  - Ollama state classifier
  - small-model selector
  - Local Agent binding detector
  - fail-closed rebind planner
  - frontend generation classifier
  - voice startup classifier
- `test_recovery_functions.py`
- `collect_ollama_evidence.py`
- `collect_local_agent_binding.py`
- `collect_frontend_voice_evidence.py`
- `snapshot_recovery_state.py`
- `test_snapshot_recovery_state.py`
- `compact_recovery_snapshot.py`
- `test_compact_recovery_snapshot.py`
- `validate_qwen_inference.py`
- `locate_voice_trigger.py`

Latest relevant isolated commits:
- deterministic classifiers: `06221b9f8236afcc0f4ff59464455968cde8d8f7`
- classifier tests: `bb42f68054586b90674e5b5fc7f86ce54da11f4f`
- callable Ollama collector: `c902458c624e684abf62d2775c871a3a1c766ef2`
- callable Local Agent collector: `c8c3e6cb053fefac5320e06b4af3a53ac9f48bb7`
- Ollama base-url collection: `c537d98a6a52095c8a489e0055e2c61bc9049443`
- frontend/voice collector: `68e42d333b45102b70cb1a8784695dd302bc9a17`
- composed snapshot: `c930635491df4a85bbeb9979977aca3ac9dbc2fe`
- snapshot tests: `b86beb72a27d877b93e1c5a126e2b1dd5c8ed0d8`
- compact snapshot: `09b21c1d50ab9f419e461539a27d5838fa4e859c`
- compact snapshot test: `859759c12d024d40b0ad624169fd6c2faf0ef02c`
- Qwen inference validator: `03c1cf194ca8a3d44550686fe7e88cb11d9deeb3`
- voice trigger locator: `df8e429e003b30bacb460f25ae48f648ffbba802`

## Current pending validation

Prepared but NOT queued due concurrency collision:
- direct Qwen inference through exact target model
- compact voice-trigger localization

The append failed closed because the permanent-control lane advanced `main` during the compare-and-swap window.

Current observed queue owner:
`ppc-accept-authority-1790815766-18357`

Do not append the recovery validation until that acceptance transaction is terminal or expired and no newer owner appears.

## Next deterministic sequence

1. refresh `open-webui/main` + queue blob;
2. verify no live concurrent queue owner;
3. issue one bounded transaction running:
   - `validate_qwen_inference.py`
   - compact `locate_voice_trigger.py`
4. verify/decrypt receipt;
5. if Qwen PASS:
   - backend/model recovery = accepted;
6. use exact voice file/line indices to remove only the unsolicited startup READY playback predicate;
7. preserve `1.3.4-nowarm` and silent cache behavior;
8. then repair presentation:
   - remove/demote v20260930.4 fixed-body hero presenter;
   - restore explicit landing-vs-chat ownership from accepted v1.4.5 lineage;
   - preserve stock loader/custom.css zero-byte invariant.

## Stop conditions

Do not:
- rebind Local Agent; it is already correctly bound to Qwen;
- use Granite;
- pull a model;
- restart Ollama while current deterministic snapshot says healthy;
- reintroduce warmSelectedVoice or `/local-voice/warm`;
- mutate stock loader/custom.css;
- compete with active permanent-control acceptance tasks.
