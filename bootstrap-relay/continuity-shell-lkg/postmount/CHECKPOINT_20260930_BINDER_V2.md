# Continuity Shell post-mount checkpoint — semantic binder v20260930.2

Date: 2026-09-30
Owner: ChatGPT iOS chat assistant session
Lane: UI recovery / presentation semantics
Concurrent-session boundary: 4 live assistant sessions; this lane remains isolated on `repair/continuity-shell-postmount-20260930`.

## Deployment receipt

User-executed installer result:

- `BASE_RESOLVED=/home/storage/781/4477781/user/webapp`
- `INDEX_BINDER_BLOCKS_REMOVED=1`
- `INDEX_MARKER=INSTALLED_V2`
- `SEMANTIC_BINDER_V2_STAGE=PASS`
- `ownership=MAPPING_ONLY_NO_PRESENTATION_CREATION`
- rollback checkpoint: `/home/storage/781/4477781/user/webapp/runtime-domains/pwa-repair-agent/backups/pre-semantic-binder-v2-20260930T123128Z`
- deployed index SHA-256: `6847852baa98889fe209ec62150612077e89f363b760fb4ee909d2aef40aa0a0`
- binder JS SHA-256: `28323668a349f2d52b1c73a307239a1fcf46abfa408be9e9e0ec2c1e8b2a0f99`
- binder CSS SHA-256: `042abfc5336fee16b2f7fe0f333ff938ac78c0c3e50968583366eaac2459a644`
- stock loader bytes: `0`
- stock custom CSS bytes: `0`
- accepted no-warm voice bridge SHA-256: `5e6d66aaef727ac3da75791c1ef411577ece1ab4573c82a752cc75315a97d140`
- public HTTP: `200`
- public marker: `PASS`
- restart required: `NO`

## Live public-asset verification

Independent public extraction after deployment confirms:

- `/static/continuity-shell-semantic-binder.js?v=20260930.2` is serving binder version `20260930.2`.
- `/static/continuity-shell-semantic-binder.css?v=20260930.2` is serving the mapping-only stylesheet.
- The binder creates no hero, READY label, footer node, chat telemetry node, Border Beam, loader path, audio path, model path, or runtime path.
- `continuity-postmount-bootstrap.js` remains post-mount and loads theme overlay, no-warm voice bridge, LCARS runtime, shell registry, and continuity controls only after stock mount.
- `pwa-voice-bridge.js` remains `1.3.4-nowarm`.
- Historical `continuity-shell-lkg.css` / `continuity-shell-lkg-mapper.js` are not public live assets.

## Corrected failure classification

Binder v20260930.1 was rejected by cross-browser/device evidence because it became an additive presentation owner. It generated a second neural hero/READY/footer layer and introduced fixed geometry that collided with the native composer, especially on desktop.

Binder v20260930.2 changes the recovery mechanism from presentation creation to semantic binding only. It maps existing live OpenWebUI/Continuity nodes onto the semantic classes expected by the accepted theme stack and rewrites the existing stock footer identity in place.

## Protected invariants

Do not modify or restore:

- stock `loader.js`
- stock `custom.css`
- `pwa-client-runtime.js`
- accepted `pwa-voice-bridge.js` / no-warm policy
- Passenger/OpenWebUI process state without serialized ownership across concurrent sessions

No restart was performed by this lane.

## Acceptance gate

Status: **DEPLOYED / STRUCTURALLY VERIFIED / VISUAL DEVICE ACCEPTANCE PENDING**

Required before advancing into active-chat/status-orb repair:

1. Safari landing page
2. Firefox landing page
3. iOS Home-Screen landing page

Acceptance criteria:

- exactly one neural hero;
- exactly one READY presentation;
- exactly one footer identity;
- no desktop hero/composer/footer collision;
- composer remains stock-owned with accepted beam/theme presentation;
- WBW and LCARS can still be selected without structural corruption;
- no unsolicited launch speech.

Do not advance the active-chat/status-orb mutation boundary until the landing gate passes.
