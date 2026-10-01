<script lang="ts">
	import OrbCanvas from './OrbCanvas.svelte';
	import {
		SHELL_TONE_PALETTES,
		resolveShellVisualState,
		type ShellPhase
	} from '../state/shellState';
	import '../styles/shell.css';

	export let phase: ShellPhase = 'ready';
	export let detail: string | undefined = undefined;
	export let size = 220;

	$: visual = resolveShellVisualState(phase, detail);
	$: palette = SHELL_TONE_PALETTES[visual.tone];
	$: heroState = phase === 'ready' ? 'connecting' : visual.orbState;
	$: canvasSize = Math.round(size * 0.9);
</script>

<section
	class="hero-orb custom-shell-motion"
	data-shell-tone={visual.tone}
	data-shell-phase={visual.phase}
	aria-live="polite"
	aria-atomic="true"
>
	<div class="hero-field" style={`--hero-size:${size}px`}>
		<div class="hero-aura" aria-hidden="true"></div>
		<div class="hero-network">
			<OrbCanvas
				state={heroState}
				engineSize={64}
				displaySize={canvasSize}
				speed={phase === 'ready' ? 0.92 : 1.04}
				tint={palette[0]}
				tint2={palette[1]}
				tint3={palette[2]}
				tintStrength={0.96}
			/>
		</div>
	</div>

	<div class="hero-copy">
		<h1>{visual.label}</h1>
		{#if visual.detail}
			<p>{visual.detail}</p>
		{/if}
	</div>
</section>

<style>
	.hero-orb {
		width: min(100%, 34rem);
		display: grid;
		justify-items: center;
		gap: 0.72rem;
		isolation: isolate;
	}

	.hero-field {
		position: relative;
		width: var(--hero-size);
		height: var(--hero-size);
		display: grid;
		place-items: center;
	}

	.hero-aura {
		position: absolute;
		inset: -18%;
		border-radius: 50%;
		background:
			radial-gradient(ellipse at 38% 42%, rgb(var(--shell-accent-rgb) / 0.25), transparent 42%),
			radial-gradient(ellipse at 64% 60%, color-mix(in srgb, var(--shell-accent-3) 19%, transparent), transparent 48%);
		filter: blur(30px) saturate(1.25);
		opacity: 0.68;
		animation: hero-breathe 5.4s ease-in-out infinite;
		z-index: -2;
	}

	.hero-network {
		position: relative;
		display: grid;
		place-items: center;
		filter:
			brightness(1.2)
			contrast(1.06)
			drop-shadow(0 0 10px rgb(var(--shell-accent-rgb) / 0.48))
			drop-shadow(0 0 26px rgba(124, 92, 255, 0.24))
			drop-shadow(0 0 42px rgba(255, 79, 216, 0.14));
		animation: network-float 7s ease-in-out infinite;
	}

	.hero-copy {
		display: grid;
		justify-items: center;
		gap: 0.34rem;
		text-align: center;
	}

	.hero-copy h1 {
		margin: 0;
		font-size: 0.72rem;
		font-weight: 680;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--shell-text);
		text-shadow: 0 0 18px rgb(var(--shell-accent-rgb) / 0.12);
	}

	.hero-copy p {
		margin: 0;
		font-size: 0.61rem;
		font-weight: 650;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--shell-accent);
		opacity: 0.88;
	}

	@keyframes hero-breathe {
		0%, 100% { transform: scale(0.96); opacity: 0.72; }
		50% { transform: scale(1.04); opacity: 1; }
	}

	@keyframes network-float {
		0%, 100% { transform: translate3d(0, 2px, 0) rotate(-0.8deg); }
		50% { transform: translate3d(0, -3px, 0) rotate(0.8deg); }
	}

	@media (max-width: 520px) {
		.hero-orb { gap: 0.62rem; }
		.hero-field { transform: scale(0.94); margin-block: -0.5rem; }
		.hero-copy h1 { font-size: 0.68rem; }
	}

	@media (prefers-reduced-motion: reduce) {
		.hero-aura,
		.hero-network { animation: none; }
	}
</style>
