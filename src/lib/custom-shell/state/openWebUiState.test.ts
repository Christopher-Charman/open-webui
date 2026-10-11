import { describe, expect, it } from 'vitest';
import { deriveShellPhase } from './openWebUiState';

describe('OpenWebUI shell activity', () => {
	it('returns ready after a completed search rather than using stale history', () => {
		expect(
			deriveShellPhase({
				generating: false,
				taskCount: 0,
				message: {
					statusHistory: [{ action: 'web_search', description: 'Searching the web' }]
				}
			})
		).toBe('ready');
	});

	it('reports an active search without text output', () => {
		expect(
			deriveShellPhase({
				generating: true,
				message: {
					statusHistory: [{ action: 'web_search' }]
				}
			})
		).toBe('searching');
	});

	it('uses emitted text over stale search history while generating', () => {
		expect(
			deriveShellPhase({
				generating: true,
				message: {
					content: 'Here is the answer',
					statusHistory: [{ action: 'web_search' }]
				}
			})
		).toBe('composing');
	});

	it('does not mistake a structured object for text output', () => {
		expect(
			deriveShellPhase({ generating: true, message: { content: { kind: 'tool-call' } } })
		).toBe('thinking');
	});

	it('distinguishes active tasks, thinking, idle, and errors', () => {
		expect(deriveShellPhase({ generating: false, taskCount: 1 })).toBe('working');
		expect(deriveShellPhase({ generating: true })).toBe('thinking');
		expect(deriveShellPhase({ generating: false })).toBe('ready');
		expect(deriveShellPhase({ generating: false, message: { error: 'failed' } })).toBe('error');
	});
});
