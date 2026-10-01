<script lang="ts">
	import OrbCanvas from './OrbCanvas.svelte';
	import { SHELL_TONE_COLORS, resolveShellVisualState, type ShellPhase } from '../state/shellState';
	import '../styles/shell.css';

	export let phase: ShellPhase = 'ready';
	export let detail: string | undefined = undefined;
	export let showDetail = false;

	$: visual = resolveShellVisualState(phase, detail);
</script>

<div
	class="chat-telemetry custom-shell-motion"
	data-shell-tone={visual.tone}
	data-shell-phase={visual.phase}
	role="status"
	aria-live="polite"
>
	<span class="orb-slot">
		<OrbCanvas
			state={visual.orbState}
			engineSize={20}
			displaySize={27}
			speed={visual.active ? 1.05 : 0.7}
			tint={SHELL_TONE_COLORS[visual.tone]}
			tintStrength={0.88}
		/>
	</span>

	<span class="copy">
		<strong>{visual.label}</strong>
		{#if showDetail}
			<small>{visual.detail}</small>
		{/if}
	</span>
	<span class:active={visual.active} class="activity-dot" aria-hidden="true"></span>
</div>

<style>
	.chat-telemetry {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		min-height: 2.6rem;
		max-width: min(20rem, calc(100vw - 7rem));
		padding: 0.34rem 0.62rem 0.34rem 0.42rem;
		border: 1px solid rgb(var(--shell-accent-rgb) / 0.34);
		border-radius: 999px;
		background: var(--shell-glass-strong);
		box-shadow:
			0 8px 24px var(--shell-shadow),
			0 0 20px rgb(var(--shell-accent-rgb) / 0.11),
			inset 0 1px 0 var(--shell-highlight);
		-webkit-backdrop-filter: blur(16px) saturate(145%);
		backdrop-filter: blur(16px) saturate(145%);
	}

	.orb-slot {
		display: grid;
		place-items: center;
		width: 1.8rem;
		height: 1.8rem;
		filter: drop-shadow(0 0 8px rgb(var(--shell-accent-rgb) / 0.34));
	}

	.copy {
		min-width: 0;
		display: flex;
		align-items: baseline;
		gap: 0.48rem;
	}

	.copy strong {
		font-size: 0.78rem;
		font-weight: 600;
		letter-spacing: -0.01em;
		color: var(--shell-text);
		white-space: nowrap;
	}

	.copy small {
		font-size: 0.58rem;
		font-weight: 650;
		letter-spacing: 0.12em;
		color: var(--shell-accent);
		white-space: nowrap;
	}

	.activity-dot {
		width: 0.38rem;
		height: 0.38rem;
		border-radius: 999px;
		background: var(--shell-accent);
		box-shadow: 0 0 10px rgb(var(--shell-accent-rgb) / 0.65);
		opacity: 0.48;
	}

	.activity-dot.active {
		opacity: 1;
		animation: telemetry-pulse 1.45s ease-in-out infinite;
	}

	@keyframes telemetry-pulse {
		0%, 100% { transform: scale(0.72); opacity: 0.48; }
		50% { transform: scale(1.18); opacity: 1; }
	}

	@media (max-width: 520px) {
		.chat-telemetry { min-height: 2.45rem; padding-right: 0.55rem; }
		.copy small { display: none; }
	}

	@media (prefers-reduced-motion: reduce) {
		.activity-dot.active { animation: none; }
	}
</style>
