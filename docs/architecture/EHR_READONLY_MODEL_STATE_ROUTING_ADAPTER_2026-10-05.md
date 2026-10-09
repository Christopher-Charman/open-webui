# EHR Transfer Task — Read-Only Model-State Routing Adapter

**Status:** DRAFT / BLOCKED ON OFFLINE BENCHMARK
**Priority:** P1

## Goal
If the offline benchmark establishes incremental value, prototype the smallest read-only adapter that exposes bounded model-state observations to the external routing controller.

## Required boundaries
- Read-only observation path.
- No activation write or model steering.
- No imported EHR threshold without local calibration.
- Sensor proposes; external controller decides.
- Preserve:
  - answerability != truth;
  - correctness readout != external verification;
  - stated confidence != hidden-state readout.

## Acceptance criteria
- [ ] Adapter record includes model/checkpoint/site/readout/calibration provenance.
- [ ] Unsupported or parity-mismatched runtime state fails closed.
- [ ] Adapter can be disabled without changing ordinary model behavior.
- [ ] Routing controller remains independently testable without the readout.
- [ ] No live promotion occurs until current host state is reacquired and existing promotion/concurrency gates pass.

## Dependency
Blocked on the offline local epistemic-routing benchmark.
