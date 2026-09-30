# Continuity Shell checkpoint — hero presenter v20260930.4

Date: 2026-09-30
Owner: ChatGPT iOS chat assistant session
Lane: UI recovery / presentation semantics

## v3 device evidence

The v3 installer completed successfully on the PowerPC host:

- BASE resolved to `/home/storage/781/4477781/user/webapp`;
- public HTTP = 200;
- `HERO_PRESENTER=PUBLIC_PASS`;
- stock loader/custom CSS remained 0 bytes;
- no Passenger restart;
- accepted voice bridge remained `1.3.4-nowarm`;
- rollback checkpoint created at `pre-landing-hero-presenter-20260930T131524Z`.

Device screenshots then established three separate defects:

1. **Desktop landing geometry failure**
   - the neural hero overlays the composer;
   - a READY presentation appears below the composer/footer region;
   - therefore v3 geometry is not cross-viewport safe.

2. **Footer rewrite failure**
   - mobile and desktop still render `Open WebUI · v0.11.3`;
   - v3 searched only direct full-text nodes and did not reliably catch the actual nested footer DOM.

3. **False landing classification**
   - an active conversation with `.message-listitem` content still received the landing hero/READY;
   - route-path-only detection is insufficient because Open WebUI can show message state while remaining on a root/new-chat style route.

Additional model-specific landing evidence shows model title/description can occupy the space immediately above the composer, so hero placement must respect nearby landing identity content rather than blindly anchoring to the prompt.

Classification: `HERO_V3_PUBLIC_PASS_DEVICE_REJECTED`.

## v4 corrective delta

v4 keeps the same bounded ownership and changes only the failing logic:

- true landing now requires **no visible `.message-listitem` conversation messages**;
- active-chat hero contamination is fail-closed;
- the composer anchor remains the canonical Open WebUI `#message-input-container`;
- hero geometry is isolated with inline `!important` coordinates and explicitly resets inherited top/bottom/transform state;
- the hero is positioned above nearby model identity text when that text occupies the composer-adjacent landing area;
- footer rewrite searches compact visible elements by normalized aggregate text, so nested footer DOM is covered;
- READY suppression is no longer restricted to being above the composer;
- presentation classes `hero-network` / `hero-aura` are no longer attached to the generated SVG/aura, avoiding historical shell geometry collisions;
- active-chat/status-orb ownership remains unchanged.

## v4 staged assets

- hero JS commit: `3ed8cac7f6d243d7082a0ea16cea833a8998b323`
- hero CSS / immutable asset pin: `69b5f84de02e127efcd592bb151795493d290564`
- guarded installer v4: `10faad033ad881dd3a16699af525cf74bf0913db`
- rollback remains: `f61d7faed252dd04817b786d47c16875025a1a81`

## Acceptance gate after v4

Check:

1. System landing, portrait;
2. System landing, landscape/desktop-width;
3. World Between Worlds landing;
4. LCARS landing;
5. model-specific landing with visible model title/description;
6. an active conversation.

Required results:

- landing: exactly one neural hero + one READY;
- hero never overlaps composer, footer, model title or description;
- footer reads `Continuity Shell · Open WebUI · v0.11.3`;
- active conversation: zero landing hero and zero landing READY;
- active-chat/status-orb behavior remains otherwise unchanged for the subsequent dedicated repair lane;
- no unsolicited launch speech.

Do not mutate active-chat telemetry until this gate passes.
