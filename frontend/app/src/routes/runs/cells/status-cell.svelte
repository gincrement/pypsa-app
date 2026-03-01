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
			case 'COMPLETED':
				return { variant: 'default', label: 'Completed' };
			case 'FAILED':
				return { variant: 'destructive', label: 'Failed' };
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
