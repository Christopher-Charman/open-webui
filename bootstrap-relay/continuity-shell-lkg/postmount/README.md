# Continuity Shell post-mount semantic binder

Recovery lane: OpenWebUI/Continuity Shell presentation semantics only.

## Current boundary — v20260930.2

Cross-browser/device testing of v20260930.1 established that its generated hero, READY label,
footer and chat-telemetry nodes duplicated presentation already owned by the accepted historical
Continuity/Neural/Orb layers. v20260930.2 therefore demotes this component to a **mapping-only
semantic binder**.

It creates no hero, READY label, footer, neural SVG, chat telemetry or Border Beam. It only maps
the protected stock OpenWebUI DOM onto the historical semantic classes expected by the accepted
Continuity Shell CSS and rewrites the existing stock footer identity in-place.

Protected invariants remain:
- stock loader.js untouched and empty;
- stock custom.css untouched and empty;
- pwa-client-runtime.js untouched;
- accepted pwa-voice-bridge.js / no-warm boundary untouched;
- no Passenger/OpenWebUI restart in this concurrent-session lane.

## Device acceptance order

Landing only first: Safari / Firefox / iOS Home-Screen. Confirm duplicate READY/footer and desktop
overlap are gone before testing active-chat telemetry. Do not advance the chat layer on a failed
landing acceptance.
