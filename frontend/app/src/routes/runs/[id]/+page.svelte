<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { runs } from '$lib/api/client.js';
	import { formatRelativeTime, formatDuration } from '$lib/utils.js';
	import type { Run, ApiError } from '$lib/types.js';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import { Skeleton } from '$lib/components/ui/skeleton';
	import { CircleAlert, ArrowLeft, Terminal } from 'lucide-svelte';
	import * as Alert from '$lib/components/ui/alert';
	import StatusCell from '../cells/status-cell.svelte';

	const runId = $derived($page.params.id as string);

	let run = $state<Run | null>(null);
	let logs = $state<string[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let streaming = $state(false);
	let streamDone = $state(false);

	let eventSource: EventSource | null = null;
	let pollInterval: ReturnType<typeof setInterval> | null = null;
	let logContainer: HTMLDivElement;

	const isTerminal = $derived(
		run && ['COMPLETED', 'FAILED', 'CANCELLED'].includes(run.status)
	);

	const duration = $derived(formatDuration(run?.started_at, run?.completed_at));

	const workflowDisplay = $derived.by(() => {
		if (!run?.workflow) return null;
		let source = run.workflow;
		if (source.startsWith('https://github.com/')) {
			source = source.replace('https://github.com/', '');
		}
		source = source.replace(/\.git$/, '');
		return source;
	});

	onMount(async () => {
		await loadRun();
		startLogStream();
	});

	onDestroy(() => {
		stopLogStream();
		if (pollInterval) clearInterval(pollInterval);
	});

	async function loadRun() {
		loading = true;
		error = null;
		try {
			run = await runs.get(runId);
		} catch (err) {
			if (!(err as ApiError).cancelled) error = (err as Error).message;
		} finally {
			loading = false;
		}
	}

	function startLogStream() {
		if (eventSource) return;

		const url = runs.logsUrl(runId);
		eventSource = new EventSource(url, { withCredentials: true });
		streaming = true;

		eventSource.onmessage = (event) => {
			logs.push(event.data);
			scrollToBottom();
		};

		eventSource.addEventListener('done', () => {
			streamDone = true;
			streaming = false;
			eventSource!.close();
			eventSource = null;
			// Refresh run data to get final status
			loadRun();
		});

		eventSource.onerror = () => {
			streaming = false;
			if (eventSource) {
				eventSource.close();
				eventSource = null;
			}
			// Start polling for status if not terminal
			const terminal = run && ['COMPLETED', 'FAILED', 'CANCELLED'].includes(run.status);
			if (!terminal) {
				startPolling();
			}
		};
	}

	function stopLogStream() {
		if (eventSource) {
			eventSource.close();
			eventSource = null;
			streaming = false;
		}
	}

	function startPolling() {
		if (pollInterval) return;
		pollInterval = setInterval(async () => {
			try {
				run = await runs.get(runId);
				if (isTerminal && pollInterval) {
					clearInterval(pollInterval);
					pollInterval = null;
				}
			} catch {
				// ignore polling errors
			}
		}, 5000);
	}

	function scrollToBottom() {
		requestAnimationFrame(() => {
			if (logContainer) {
				logContainer.scrollTop = logContainer.scrollHeight;
			}
		});
	}
</script>

<div class="min-h-screen">
	<div class="max-w-[80rem] mx-auto py-8">
		<!-- Back button -->
		<Button variant="ghost" class="mb-4 gap-2" onclick={() => goto('/runs')}>
			<ArrowLeft class="h-4 w-4" />
			Back to Runs
		</Button>

		{#if error}
			<Alert.Root variant="destructive" class="mb-4">
				<CircleAlert class="size-4" />
				<Alert.Title>Error</Alert.Title>
				<Alert.Description>{error}</Alert.Description>
			</Alert.Root>
		{/if}

		{#if loading && !run}
			<!-- Loading skeleton -->
			<div class="bg-card rounded-lg border border-border p-6 mb-4">
				<div class="flex items-center gap-4 mb-4">
					<Skeleton class="h-6 w-20 rounded-full" />
					<Skeleton class="h-5 w-64" />
				</div>
				<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
					<Skeleton class="h-4 w-32" />
					<Skeleton class="h-4 w-24" />
					<Skeleton class="h-4 w-28" />
					<Skeleton class="h-4 w-20" />
				</div>
			</div>
			<Skeleton class="h-96 w-full rounded-lg" />
		{:else if run}
			<!-- Run header -->
			<div class="bg-card rounded-lg border border-border p-6 mb-4">
				<div class="flex items-center gap-4 mb-4">
					<StatusCell {run} />
					<h1 class="text-lg font-semibold">
						{#if workflowDisplay}
							{workflowDisplay}
						{:else}
							Run {run.id.slice(0, 8)}
						{/if}
					</h1>
				</div>

				<div class="grid grid-cols-2 md:grid-cols-4 gap-y-3 gap-x-6 text-sm text-muted-foreground">
					{#if run.configfile}
						<div>
							<span class="font-medium text-foreground">Config:</span>
							{run.configfile}
						</div>
					{/if}
					{#if run.git_ref || run.git_sha}
						<div>
							<span class="font-medium text-foreground">Ref:</span>
							{run.git_ref || ''}{run.git_sha ? `@${run.git_sha.slice(0, 8)}` : ''}
						</div>
					{/if}
					{#if duration}
						<div>
							<span class="font-medium text-foreground">Duration:</span>
							{duration}
						</div>
					{/if}
					<div>
						<span class="font-medium text-foreground">Created:</span>
						{formatRelativeTime(run.created_at)}
					</div>
					{#if run.exit_code !== null && run.exit_code !== undefined}
						<div>
							<span class="font-medium text-foreground">Exit code:</span>
							{run.exit_code}
						</div>
					{/if}
				</div>
			</div>

			<!-- Logs -->
			<div class="bg-card rounded-lg border border-border overflow-hidden">
				<div class="flex items-center gap-2 px-4 py-3 border-b border-border">
					<Terminal class="h-4 w-4 text-muted-foreground" />
					<span class="text-sm font-medium">Logs</span>
					{#if streaming}
						<span class="ml-auto text-xs text-muted-foreground flex items-center gap-1.5">
							<span class="h-2 w-2 rounded-full bg-green-500 animate-pulse"></span>
							Streaming
						</span>
					{/if}
				</div>
				<div
					bind:this={logContainer}
					class="bg-zinc-950 text-zinc-200 p-4 font-mono text-xs leading-5 overflow-y-auto"
					style="max-height: 70vh; min-height: 20rem;"
				>
					{#if logs.length === 0}
						<span class="text-zinc-500">
							{#if streaming}
								Waiting for logs...
							{:else if isTerminal}
								No logs available.
							{:else}
								Connecting...
							{/if}
						</span>
					{:else}
						{#each logs as line, i}
							<div class="whitespace-pre-wrap hover:bg-zinc-900/50">{line}</div>
						{/each}
					{/if}
				</div>
			</div>
		{/if}
	</div>
</div>
