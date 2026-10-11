import type { ShellPhase } from './shellState';

interface OpenWebUiStatusEntry {
	action?: string;
	description?: string;
}

interface OpenWebUiMessage {
	error?: unknown;
	statusHistory?: OpenWebUiStatusEntry[];
	content?: unknown;
}

export interface OpenWebUiActivity {
	generating: boolean;
	taskCount?: number;
	message?: OpenWebUiMessage;
}

const SEARCH_ACTIONS = new Set(['web_search', 'web_search_queries_generated', 'knowledge_search']);

export function deriveShellPhase(activity: OpenWebUiActivity): ShellPhase {
	const message = activity.message;
	if (message?.error) return 'error';

	const statusHistory = message?.statusHistory ?? [];
	const latest = statusHistory.at?.(-1) ?? statusHistory[statusHistory.length - 1];
	const action = latest?.action ?? '';
	const description = String(latest?.description ?? '').toLowerCase();

	const hasActiveTasks = (activity.taskCount ?? 0) > 0;
	// Status history is retained after a tool run; it must not override current activity.
	if (!activity.generating && !hasActiveTasks) return 'ready';
	if (activity.generating && typeof message?.content === 'string' && message.content.trim())
		return 'composing';
	if (SEARCH_ACTIONS.has(action) || description.includes('search')) return 'searching';
	if (activity.generating) return 'thinking';
	return 'working';
}
