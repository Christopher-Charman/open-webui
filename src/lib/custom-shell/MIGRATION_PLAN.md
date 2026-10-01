# Custom Shell Migration Plan

## Wave 0 — foundation
Status: staged.
- Shared semantic state contract (`shellState`).
- Real OpenWebUI activity adapter (`openWebUiState`), no DOM polling.
- Framework-neutral thinking-orbs geometry vendored with MIT provenance.
- Svelte canvas binding and spectral design tokens.

## Wave 1 — primary chat surfaces
Status: active.
- Replace landing composition with independent `HeroOrb`; never reuse chat telemetry pill.
- Add compact `ChatTelemetry` to active chat only.
- Recompose prompt around one parent focus/chrome surface, following shadcn InputGroup semantics.
- Treat attachments, integrations/modes, model choice, and submit/voice as explicit prompt subregions.
- Preserve all OpenWebUI input handlers, upload paths, shortcuts, focus behavior and permissions.

## Wave 2 — messages, tools and status
- Build custom message surface from OpenWebUI message semantics, informed by Fragments `Message`.
- Collapse verbose tool/status output into progressive-disclosure instrumentation.
- Preserve code blocks, citations, files, source metadata and accessible expansion controls.
- Use gooey motion only for live grouping/state transitions, never dense text.

## Wave 3 — navigation and workspace chrome
- Replace stock visual header/sidebar composition while preserving routes, menus and permissions.
- Unify mobile top-bar, desktop sidebar and overflow controls under shared shell tokens.
- Progressive disclosure by default; infrastructure metadata appears on demand.

## Wave 4 — reusable registry
- Promote accepted Svelte primitives into the custom-shell registry with provenance and version gates.
- Reuse suitable primitives in Terminal PWA, LCARS and later NEC only after project-specific adoption.
- Do not import React merely to consume reference projects; port semantics/accessibility natively.

## Acceptance discipline
`STAGED_SOURCE != BUILD_PASS != LIVE_DEPLOYED != BROWSER_ACCEPTED`.
Every wave requires rollback, source/build checks, runtime regression checks and mobile visual evidence.
