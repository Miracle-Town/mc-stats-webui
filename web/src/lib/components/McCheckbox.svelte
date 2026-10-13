<script lang="ts">
	let {
		checked = $bindable(false),
		label
	}: {
		checked?: boolean;
		label: string;
	} = $props();
</script>

<label class="checkbox">
	<input type="checkbox" bind:checked />
	{label}
</label>

<style>
	.checkbox {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		color: var(--color-muted);
		font-size: 0.78rem;
		cursor: pointer;
	}

	.checkbox input {
		appearance: none;
		flex: 0 0 1.25rem;
		width: 1.25rem;
		height: 1.25rem;
		margin: 0;
		background-color: var(--button-face);
		background-position: center;
		background-repeat: no-repeat;
		background-size: 100% 100%;
		border: 2px solid var(--button-border);
		border-radius: 0;
		box-shadow: inset 2px 2px 0 var(--button-highlight), inset -2px -2px 0 var(--button-shadow);
		cursor: pointer;
	}

	.checkbox input:checked {
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' shape-rendering='crispEdges'%3E%3Cpath fill='%233f3f3f' d='M4 8h2v2h2V8h2V6h2V4h2v4h-2v2h-2v2H8v2H6v-2H4z'/%3E%3Cpath fill='%23fff' d='M3 7h2v2h2V7h2V5h2V3h2v4h-2v2H9v2H7v2H5v-2H3z'/%3E%3C/svg%3E");
	}

	.checkbox:hover input,
	.checkbox input:focus-visible {
		background-color: var(--button-face-hover);
		border-color: var(--button-border-hover);
	}

	.checkbox input:focus-visible {
		outline: 2px solid var(--button-border-hover);
		outline-offset: 2px;
	}

</style>
