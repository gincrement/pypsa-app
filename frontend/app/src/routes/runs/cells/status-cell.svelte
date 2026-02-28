<script>
	import { Badge } from '$lib/components/ui/badge';

	let { run } = $props();

	const statusConfig = $derived.by(() => {
		switch (run.status) {
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
