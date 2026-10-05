# EHR Transfer Task — Offline Local Epistemic-Routing Benchmark

**Status:** DRAFT PLANNING ONLY / NO LIVE RUNTIME MUTATION
**Priority:** P1

## Goal
Test whether model-state/readout telemetry adds useful routing value on the actual local-model runtime before any production integration.

## Decisions under test
- ANSWER
- RETRIEVE
- VERIFY
- ROUTE_TO_SPECIALIST
- ABSTAIN / PRESERVE_UNRESOLVED

## Method
- Use captured/offline prompts first.
- Bind every arm to exact model/checkpoint/digest, context policy and runtime configuration.
- Compare readout-assisted routing with simple baselines/heuristics and suitable null/permuted controls.
- Keep model stated confidence separate from any internal readout.
- Measure both useful routing gain and unnecessary escalation/refusal cost.

## Acceptance criteria
- [ ] Protected live frontend/runtime baseline is not mutated.
- [ ] Exact model/runtime identity recorded for every arm.
- [ ] Baseline and control policies included.
- [ ] Calibration is local to evaluated model/checkpoint/runtime.
- [ ] Benefit and false-escalation/refusal cost are reported.
- [ ] Negative result can terminate the integration path.

## Out of scope
- Activation writes or steering.
- Presentation/theme/voice changes.
- Production routing changes.
