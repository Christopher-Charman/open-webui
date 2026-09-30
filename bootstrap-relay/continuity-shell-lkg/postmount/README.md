# Continuity Shell post-mount semantic binder

Recovery lane: OpenWebUI/Continuity Shell presentation only.

## Boundary

This packet reconstructs the missing semantic DOM/state layer above the accepted stock OpenWebUI 0.11.3 mount. It does not restore or modify stock loader.js, stock custom.css, pwa-client-runtime.js, the accepted pwa-voice-bridge.js 1.3.4-nowarm, immutable application bundles, Passenger/controller, or the native control-plane receiver.

The existing accepted continuity-theme-overlay.css and lcars-theme.css remain presentation authorities. This binder supplies the semantic classes and owned elements they expect.

## Recovered historical contract

The surviving compiled Svelte writer established custom-shell-landing-prompt, chat-telemetry custom-shell-motion, role=status, aria-live=polite, orb-slot, semantic phase/detail state, default phase=ready, and telemetry orb geometry engineSize=20 / displaySize=27.

## Concurrency

Development is isolated on branch repair/continuity-shell-postmount-20260930. The installer deliberately does not restart Passenger/OpenWebUI; any restart is a separate serialized operation because three assistant sessions are live.
