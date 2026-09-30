# OpenWebUI accepted-stack recovery checkpoint — 2026-09-30

Status: staged, not yet applied to live runtime.

## Trigger

Device evidence after the semantic-binder / hero-presenter reconstruction showed broad regressions relative to the last accepted shell:

- landing hero no longer retained the accepted +50% scale;
- landing hero dynamics/presentation diverged from the accepted neural-material shell;
- desktop geometry could place the hero over the composer;
- active-chat views could receive landing presentation;
- chat/status orb presentation diverged from accepted v1.4.5 behavior;
- footer identity regressed to stock Open WebUI text;
- theme/sidebar presentation regressed;
- LCARS remained present but presentation composition diverged;
- Majel Computer playback became unreliable across the last several iterations.

The reconstruction path is therefore superseded as the immediate recovery authority.

## Canonical evidence recovered from repository history

The repository contains an explicit device-verified voice checkpoint:

`OPENWEBUI_POSTMOUNT_UI_VOICE_CHECKPOINT_20260930.md`

It records:

- `DEVICE_VERIFIED_GOOD`;
- `VOICE_SELECTION_AND_PLAYBACK = PASS`;
- `VOICE = FUNCTIONING_AS_EXPECTED`;
- voice bridge `1.3.4-nowarm`;
- no automatic voice warm calls;
- themes System / Dark / OLED Dark / World Between Worlds / LCARS;
- voices Ahsoka Hybrid / Ahsoka Piper / Cortana / Majel Computer.

The accepted orb lineage is also explicitly preserved:

- commit `bc65de4f63531e36265e4f4e575a2d73cf1c0498` — orb + Border Beam v1.4.5;
- commit `2fa5b68f901547b85c8083e73d28ad6404df0069` — requested landing hero +50%;
- commit `9799d8b863352d1531bb9d89adcbdbb93e20ae7d` — guarded public apply of v1.4.5 + hero-150;
- commit `c2d744d1a5d463177df9626c56b4f6e0cd367b7c` — restored accepted neural-material presentation, dynamic neural sphere, strong spectral composer beam, round top controls, Continuity Shell footer, active-chat v1.4.5 left unchanged.

## Recovery strategy

Do not continue patching the rejected semantic-binder / hero-presenter reconstruction.

Rebase presentation in four pinned phases:

1. exact official Open WebUI 0.11.3 frontend from commit `350b0e44b5082191ce6fe4bf4c9a0819d79a11f6`;
2. device-verified UI/voice layer from `37209364b2b60366c345a7a8db416b6b3bc58b3c`;
3. accepted v1.4.5 orb/Border Beam + hero-150 from `9799d8b863352d1531bb9d89adcbdbb93e20ae7d`;
4. accepted neural-material presentation from `c2d744d1a5d463177df9626c56b4f6e0cd367b7c`.

Composite guarded restore:

`bootstrap-relay/accepted-stack-restore-20260930/apply.sh`

Staging commit:

`e690a01c121c7670daef4cd1a671725f5d19246c`

The composite restore also performs a non-audible Majel synthesis probe against the local TTS service. It generates audio bytes but does not play them. Automatic launch voice warming remains forbidden.

## Concurrency boundary

The restore takes a local filesystem repair lock:

`runtime-domains/pwa-repair-agent/.accepted-stack-restore.lock`

Scope is limited to OpenWebUI frontend presentation + voice assets. It does not modify:

- terminal access;
- Remote MCP work;
- backend chat data;
- authentication data;
- concurrency repository work.

Because multiple assistant sessions are active, no additional OpenWebUI presentation mutator should run during the restore.

## Superseded reconstruction

The following staged reconstruction work remains in Git history for forensics but is no longer the recovery authority:

- semantic binder;
- landing hero presenter v3/v4;
- their device-acceptance checkpoints.

They must not be layered on top of the accepted-stack restore before fresh device acceptance.

## Acceptance gate

After restore, validate:

- System landing portrait;
- System landing desktop/landscape;
- World Between Worlds landing;
- LCARS landing + Continuity Controls;
- model-specific landing;
- active conversation;
- sidebar;
- Majel read-aloud.

Required:

- one dynamic neural hero on landing only;
- +50% accepted hero sizing;
- strong spectral composer beam;
- Continuity Shell footer;
- no landing hero/READY in active chat;
- accepted compact chat orb/status telemetry;
- no unsolicited launch speech;
- Majel synthesis probe PASS and device playback PASS.
