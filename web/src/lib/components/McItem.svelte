<script lang="ts">
	import { itemLetter, itemSprite } from '$lib/mc/items';
	import { atlasStatus, loadAtlas } from '$lib/mc/atlas.svelte';

	let { id, compact = false }: { id: string; compact?: boolean } = $props();
	const sprite = $derived(itemSprite(id));
	const displaySize = $derived(compact ? 1.5 : 2.25);
	const ready = $derived(sprite && atlasStatus(sprite.url) === 'ready');

	$effect(() => {
		if (sprite) loadAtlas(sprite.url);
	});
</script>

<span class="frame" class:compact aria-hidden="true">
	{#if sprite && ready}
		<span
			class="icon"
			class:compact
			style:background-image={`url("${sprite.url}")`}
			style:background-size={`${sprite.width / sprite.size * displaySize}rem ${sprite.height / sprite.size * displaySize}rem`}
			style:background-position={`${-sprite.x / sprite.size * displaySize}rem ${-sprite.y / sprite.size * displaySize}rem`}
		></span>
	{:else}
		<span class="letter" class:compact>{itemLetter(id)}</span>
	{/if}
</span>

<style>
	.frame {
		position: relative;
		width: 2.25rem;
		height: 2.25rem;
		flex-shrink: 0;
		display: inline-grid;
		place-items: center;
	}

	.frame.compact {
		width: 1.5rem;
		height: 1.5rem;
	}

	.icon {
		width: 2.25rem;
		height: 2.25rem;
		image-rendering: pixelated;
		background-repeat: no-repeat;
		flex-shrink: 0;
		display: block;
	}

	.letter {
		width: 2.25rem;
		height: 2.25rem;
		display: grid;
		place-items: center;
		color: var(--color-gold);
		background: var(--slot-bg);
		border: 2px solid var(--color-border);
		font-size: 1rem;
		flex-shrink: 0;
	}

	.icon.compact,
	.letter.compact {
		width: 1.5rem;
		height: 1.5rem;
	}

	.letter.compact {
		font-size: 0.8rem;
	}
</style>
