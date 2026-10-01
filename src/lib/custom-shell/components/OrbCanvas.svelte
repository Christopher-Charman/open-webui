<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { MODE_DRAWS } from '../vendor/thinking-orbs/engine/registry';
	import { resolvePreset } from '../vendor/thinking-orbs/presets';
	import type { OrbSize, OrbState } from '../vendor/thinking-orbs/types';

	export let state: OrbState = 'breathing';
	export let displaySize = 64;
	export let engineSize: OrbSize = 64;
	export let speed = 1;
	export let paused = false;
	export let tint: string | null = null;
	export let tint2: string | null = null;
	export let tint3: string | null = null;
	export let tintStrength = 0.86;

	let canvas: HTMLCanvasElement;
	let ctx: CanvasRenderingContext2D | null = null;
	let raf = 0;
	let visible = true;
	let dark = true;
	let reducedMotion = false;
	let io: IntersectionObserver | null = null;
	let themeObserver: MutationObserver | null = null;
	let media: MediaQueryList | null = null;

	$: preset = resolvePreset(state, engineSize);
	$: if (canvas) resizeCanvas();

	function resizeCanvas() {
		const dpr = Math.min(2, window.devicePixelRatio || 1);
		canvas.width = Math.round(displaySize * dpr);
		canvas.height = Math.round(displaySize * dpr);
	}

	function resolveTheme() {
		const root = document.documentElement;
		if (root.dataset.theme === 'light' || root.classList.contains('light')) dark = false;
		else if (root.dataset.theme === 'dark' || root.classList.contains('dark')) dark = true;
		else dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
	}

	function frame(now: number) {
		if (!ctx || !canvas) return;
		const dpr = Math.min(2, window.devicePixelRatio || 1);
		const scale = displaySize / engineSize;
		ctx.setTransform(dpr * scale, 0, 0, dpr * scale, 0, 0);
		ctx.clearRect(0, 0, engineSize, engineSize);
		const draw = MODE_DRAWS[preset.mode];
		const t = reducedMotion ? 0.6 : (now / 1000) * preset.speed * speed;
		draw(ctx, engineSize, t, dark, preset.opts);

		if (tint) {
			ctx.save();
			ctx.globalCompositeOperation = 'source-atop';
			ctx.globalAlpha = tintStrength;
			if (tint2 || tint3) {
				const gradient = ctx.createLinearGradient(0, 0, engineSize, engineSize);
				gradient.addColorStop(0, tint);
				gradient.addColorStop(0.54, tint2 ?? tint);
				gradient.addColorStop(1, tint3 ?? tint2 ?? tint);
				ctx.fillStyle = gradient;
			} else {
				ctx.fillStyle = tint;
			}
			ctx.fillRect(0, 0, engineSize, engineSize);
			ctx.restore();
		}
	}

	function loop(now: number) {
		frame(now);
		if (!paused && visible && document.visibilityState !== 'hidden' && !reducedMotion) {
			raf = requestAnimationFrame(loop);
		}
	}

	function restart() {
		cancelAnimationFrame(raf);
		frame(performance.now());
		if (!paused && visible && document.visibilityState !== 'hidden' && !reducedMotion) {
			raf = requestAnimationFrame(loop);
		}
	}

	onMount(() => {
		ctx = canvas.getContext('2d');
		resizeCanvas();
		resolveTheme();
		media = window.matchMedia('(prefers-reduced-motion: reduce)');
		reducedMotion = media.matches;

		themeObserver = new MutationObserver(() => {
			resolveTheme();
			restart();
		});
		themeObserver.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ['class', 'data-theme']
		});

		io = new IntersectionObserver(([entry]) => {
			visible = entry.isIntersecting;
			restart();
		});
		io.observe(canvas);

		const onVisibility = () => restart();
		document.addEventListener('visibilitychange', onVisibility);

		const onMotion = () => {
			reducedMotion = media?.matches ?? false;
			restart();
		};
		media.addEventListener?.('change', onMotion);
		restart();

		return () => {
			cancelAnimationFrame(raf);
			io?.disconnect();
			themeObserver?.disconnect();
			media?.removeEventListener?.('change', onMotion);
			document.removeEventListener('visibilitychange', onVisibility);
		};
	});

	onDestroy(() => cancelAnimationFrame(raf));
</script>

<canvas
	bind:this={canvas}
	aria-hidden="true"
	class="orb-canvas"
	style:width={`${displaySize}px`}
	style:height={`${displaySize}px`}
></canvas>

<style>
	.orb-canvas {
		display: block;
		max-width: 100%;
		aspect-ratio: 1;
		contain: layout paint style;
	}
</style>
