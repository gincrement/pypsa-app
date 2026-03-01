<script lang="ts">
	import { FolderSync, LoaderCircle } from 'lucide-svelte';
	import { Button } from '$lib/components/ui/button';

	interface ScanButtonProps {
		scanning?: boolean;
		variant?: 'default' | 'link' | 'destructive' | 'secondary' | 'outline' | 'ghost';
		size?: 'default' | 'sm' | 'lg' | 'icon' | 'icon-sm' | 'icon-lg';
		onScan?: () => void;
	}

	let { scanning = false, variant = 'outline', size = 'sm', onScan }: ScanButtonProps = $props();
</script>

<Button {variant} {size} onclick={onScan} disabled={scanning}>
	{#if scanning}
		<LoaderCircle class="h-4 w-4 mr-2 animate-spin" />
		Scanning...
	{:else}
		<FolderSync class="h-4 w-4 mr-2" />
		Scan
	{/if}
</Button>
