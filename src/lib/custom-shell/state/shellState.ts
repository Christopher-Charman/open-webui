import type { OrbState } from '../vendor/thinking-orbs/types';

export type ShellPhase =
	| 'ready'
	| 'thinking'
	| 'working'
	| 'searching'
	| 'composing'
	| 'listening'
	| 'connecting'
	| 'error';

export type ShellTone = 'cyan' | 'violet' | 'magenta' | 'amber' | 'red';

export const SHELL_TONE_COLORS: Record<ShellTone, string> = {
	cyan: '#35e7ff',
	violet: '#9a6cff',
	magenta: '#ff4fd8',
	amber: '#ffb347',
	red: '#ff5f73'
};

export const SHELL_TONE_PALETTES: Record<ShellTone, [string, string, string]> = {
	cyan: ['#35e7ff', '#7c5cff', '#ff4fd8'],
	violet: ['#9a6cff', '#5ddcff', '#ff4fd8'],
	magenta: ['#ff4fd8', '#9a6cff', '#35e7ff'],
	amber: ['#ffb347', '#ff6b8a', '#9a6cff'],
	red: ['#ff5f73', '#ff9a5c', '#9a6cff']
};

export interface ShellVisualState {
	phase: ShellPhase;
	label: string;
	detail: string;
	orbState: OrbState;
	tone: ShellTone;
	active: boolean;
}

const PHASES: Record<ShellPhase, Omit<ShellVisualState, 'phase' | 'detail'>> = {
	ready: { label: 'Ready', orbState: 'breathing', tone: 'cyan', active: false },
	thinking: { label: 'Thinking…', orbState: 'solving', tone: 'violet', active: true },
	working: { label: 'Working…', orbState: 'working', tone: 'cyan', active: true },
	searching: { label: 'Searching…', orbState: 'searching', tone: 'violet', active: true },
	composing: { label: 'Composing…', orbState: 'composing', tone: 'magenta', active: true },
	listening: { label: 'Listening…', orbState: 'listening', tone: 'cyan', active: true },
	connecting: { label: 'Connecting…', orbState: 'connecting', tone: 'amber', active: true },
	error: { label: 'Degraded', orbState: 'shaping', tone: 'red', active: false }
};

const DEFAULT_DETAIL: Record<ShellPhase, string> = {
	ready: '',
	thinking: 'REASONING',
	working: 'EXECUTING',
	searching: 'RETRIEVAL',
	composing: 'SYNTHESIS',
	listening: 'VOICE INPUT',
	connecting: 'CONNECTING',
	error: 'ATTENTION REQUIRED'
};

export function resolveShellVisualState(
	phase: ShellPhase,
	detail?: string
): ShellVisualState {
	return { phase, ...PHASES[phase], detail: detail ?? DEFAULT_DETAIL[phase] };
}
