<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import type { Run } from '$lib/types.js';

	type BadgeVariant = 'default' | 'secondary' | 'destructive' | 'outline';

	let { run }: { run: Run } = $props();

	const statusConfig = $derived.by((): { variant: BadgeVariant; label: string; class?: string } => {
		const status = run.status as string;
		switch (status) {
			case 'RUNNING':
				return { variant: 'secondary', label: 'Running', class: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 border-transparent' };
			case 'UPLOADING':
				return { variant: 'secondary', label: 'Uploading', class: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 border-transparent' };
			case 'COMPLETED':
				return { variant: 'default', label: 'Completed' };
			case 'FAILED':
				return { variant: 'destructive', label: 'Failed' };
			case 'ERROR':
				return { variant: 'destructive', label: 'Error', class: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200 border-transparent' };
			case 'CANCELLED':
				return { variant: 'outline', label: 'Cancelled' };
			case 'SETUP':
				return { variant: 'secondary', label: 'Setup' };
			case 'PENDING':
			default:
				return { variant: 'secondary', label: 'Pending' };
		}
	});
</script>

<Badge variant={statusConfig.variant} class={statusConfig.class || ''}>
	{statusConfig.label}
</Badge>
