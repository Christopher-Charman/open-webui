// Vendored from Christopher-Charman/thinking-orbs @ de85557.
// React-only component props intentionally omitted: this OpenWebUI port
// consumes the renderer engine as framework-neutral geometry.

export type OrbState =
	| 'working'
	| 'searching'
	| 'solving'
	| 'listening'
	| 'connecting'
	| 'weaving'
	| 'composing'
	| 'breathing'
	| 'shaping';

export type OrbSize = 64 | 20;
