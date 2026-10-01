# Custom Shell Architecture

## Governing rule
OpenWebUI and adopted OSS projects are implementation substrates, not product boundaries.
Preserve proven backend/session/tool/provider semantics; freely replace presentation and interaction layers.

## Component split
- `HeroOrb`: landing-only spatial identity; large free-standing orb, gooey field, strong spectral colour.
- `ChatTelemetry`: compact operational status for active conversations.
- `OrbCanvas`: framework-native Svelte renderer over the pure thinking-orbs geometry engine.
- `shellState`: shared semantic state contract; presentation components interpret it independently.

## Source inspirations
- `Christopher-Charman/thinking-orbs`: geometry engine; vendored MIT source, pinned provenance.
- `Christopher-Charman/ui`: Fragments AI/layout interaction vocabulary; adapted, not runtime-imported.
- `Christopher-Charman/ui-shadcn`: open-code / registry model; adapted, not runtime-imported.
- Libraries.dev primitives: motion/spatial/gooey interaction language; selective adaptation only.

## Integration boundary
Landing composition belongs in OpenWebUI `Placeholder.svelte`.
Active chat telemetry belongs in `Chat.svelte` and derives state from OpenWebUI data, never DOM polling.
Message, prompt, tool and navigation surfaces will migrate incrementally behind preserved functional contracts.
