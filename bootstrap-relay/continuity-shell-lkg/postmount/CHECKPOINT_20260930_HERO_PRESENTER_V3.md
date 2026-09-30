# Continuity Shell checkpoint — landing hero presenter v20260930.3

Date: 2026-09-30
Owner: ChatGPT iOS chat assistant session
Lane: UI recovery / presentation semantics
Concurrent-session boundary: four live assistant sessions; this lane remains isolated on `repair/continuity-shell-postmount-20260930`.

## Device result: semantic binder v2 rejected as incomplete

Cross-browser/device evidence after semantic binder `20260930.2` establishes:

- semantic/theme mapping survives;
- System/WBW/LCARS backgrounds and prompt treatment survive;
- Continuity Controls survive;
- unsolicited launch speech remains absent;
- stock loader/custom CSS remain outside presentation ownership;
- **landing neural hero count = 0**;
- a single existing READY label remains;
- the visible footer has fallen back to stock `Open WebUI · v0.11.3`.

Classification: `BINDER_V2_STRUCTURALLY_SAFE_VISUALLY_INCOMPLETE`.

The root cause is now bounded: v2 is deliberately mapping-only, while the historical compiled presentation writer that created the landing hero is no longer active in the live frontend. Mapping cannot restore an absent presentation node.

## Historical closure

Binder v1 is not to be replayed unchanged. It failed because it:

- created hero + READY + footer as additive owners;
- used fixed viewport geometry;
- collided with composer/footer on desktop;
- duplicated presentation already emitted elsewhere.

Binder v2 corrected that by removing all presentation creation, but over-corrected to zero hero.

Novel delta for v3:

- create **only** the missing landing neural hero presentation;
- suppress the pre-existing landing READY while v3 owns one READY, instead of duplicating it;
- rewrite the existing footer text in place only; never create a second footer;
- use compositor-relative dynamic placement with no layout shift;
- leave active-chat telemetry/status orb untouched until landing acceptance passes;
- leave semantic binder v2 in place.

## Staged implementation

Presentation assets:

- JS commit: `6061fc63b8c43ca7aacb808e390503ee3d5c5bcc`
- CSS commit / immutable asset pin: `1c70650d38d34f34b04e42b37971c8d4c367ec43`

Guarded installer:

- commit: `0b1ef6a1b72a42415b6a57998b05de0e8ace90fb`
- path: `bootstrap-relay/continuity-shell-lkg/postmount/apply-hero-presenter.sh`

Rollback:

- commit: `f61d7faed252dd04817b786d47c16875025a1a81`
- path: `bootstrap-relay/continuity-shell-lkg/postmount/rollback-hero-presenter.sh`

## Protected invariants

The installer fail-closes unless all of these remain true:

- stock `loader.js` = 0 bytes;
- stock `custom.css` = 0 bytes;
- accepted `pwa-voice-bridge.js` SHA-256 remains `5e6d66aaef727ac3da75791c1ef411577ece1ab4573c82a752cc75315a97d140`;
- voice bridge remains `1.3.4-nowarm`;
- no voice warm endpoint / warmSelectedVoice / observer warm path;
- semantic binder v2 remains installed;
- no `pwa-client-runtime` restore;
- no Passenger restart;
- no active-chat/status-orb mutation.

## Execution-surface note

For this session only:

- owned/direct PowerPC terminal/MCP route: not exposed to this ChatGPT session;
- Gateway server definitions: present but not ready for ordinary execution;
- Desktop Commander device: online, but remote call allowance reports 0% remaining.

Therefore deployment is staged but not executed by this session. Manual Web Terminal invocation is a bounded fallback for this one deployment, not a change to the durable execution architecture.

## Next gate

Run the guarded hero-presenter installer, then device-test landing only:

1. System
2. World Between Worlds
3. LCARS

Required landing acceptance:

- exactly one neural mesh hero;
- exactly one READY;
- no dark solid-disc orb;
- no hero/composer/footer collision;
- one `Continuity Shell · Open WebUI · v0.11.3` footer;
- prompt beam remains accepted;
- no unsolicited speech.

Do not advance active-chat/status-orb repair until this landing gate passes.
