# Local Agent small-model decision — 2026-09-30

Status: TARGET_SELECTED / QWEN_PRESENT_IN_OLLAMA / LIVE_BINDING_READ_PENDING

## User directive

Do not use Granite for Local Agent / Mini C-Agent.

Use one of the previously referenced useful smaller models.

## Selected target

`qwen2.5-coder:1.5b-instruct-q4_K_M`

Why:
- exact Ollama tag exists;
- 1.54B / Q4_K_M / approximately 986 MB;
- code-specific instruction model;
- substantially below the prior Qwen 4B memory failure boundary;
- appropriate for bounded coding/tool work.

Owned runtime receipt `owui-qwen-binding-check-1790807927` verified:
- Ollama HTTP = 200;
- model count = 15;
- target tag is already installed;
- therefore no pull/download is required.

The same inventory also contained:
- `qwen3:4b-instruct`;
- `qwen2.5-coder:7b`;
- `qwen3:4b`;
- `deepseek-r1:1.5b-qwen-distill-q8_0`;
- `deepseek-r1:1.5b`;
- Granite variants;
- `lfm2.5:8b-a1b-q4_K_M`.

The first probe's DB section failed after inventory proof because of a local script variable typo. It did not mutate runtime state.

## Fallback

`deepseek-r1:1.5b` only if Qwen binding cannot be used.

DeepSeek is retained as a narrow specialist because archived testing confirmed successful local execution but weak provenance/speaker/conversational binding.

## Mutation gate

Do not rebind until:
1. current Local Agent workspace row is read;
2. exactly one Local Agent / Mini C-Agent row is identified;
3. current `base_model_id` is recorded;
4. Qwen target remains present in Ollama.

Planned mutation is limited to:
- that row's `base_model_id`;
- `updated_at`.

Use compare-and-swap semantics and verify readback.

No model pull, preset recreation, service restart, or broad DB mutation is authorized by this decision.
