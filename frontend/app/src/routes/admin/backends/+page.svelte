<script lang="ts">
	import { onMount } from 'svelte';
	import { admin } from '$lib/api/client.js';
	import { formatDate } from '$lib/utils.js';
	import { Server, Users, Plus, Trash2 } from 'lucide-svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as Table from '$lib/components/ui/table';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Badge } from '$lib/components/ui/badge';
	import { toast } from 'svelte-sonner';
	import type { Backend, User } from '$lib/types.js';

	let backends = $state<Backend[]>([]);
	let loading = $state(true);

	// User assignment dialog
	let selectedBackend = $state<Backend | null>(null);
	let assignedUsers = $state<User[]>([]);
	let allUsers = $state<User[]>([]);
	let dialogOpen = $state(false);
	let usersLoading = $state(false);

	onMount(async () => {
		await loadBackends();
	});

	async function loadBackends() {
		loading = true;
		try {
			backends = await admin.listBackends();
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			loading = false;
		}
	}

	async function openUserDialog(backend: Backend) {
		selectedBackend = backend;
		dialogOpen = true;
		usersLoading = true;
		try {
			const [users, assigned] = await Promise.all([
				admin.listUsers(0, 200),
				admin.listBackendUsers(backend.id)
			]);
			allUsers = users.data;
			assignedUsers = assigned;
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			usersLoading = false;
		}
	}

	async function assignUser(userId: string) {
		if (!selectedBackend) return;
		try {
			await admin.assignUserToBackend(selectedBackend.id, userId);
			assignedUsers = await admin.listBackendUsers(selectedBackend.id);
			toast.success('User assigned');
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	async function unassignUser(userId: string) {
		if (!selectedBackend) return;
		try {
			await admin.unassignUserFromBackend(selectedBackend.id, userId);
			assignedUsers = await admin.listBackendUsers(selectedBackend.id);
			toast.success('User removed');
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	function isAssigned(userId: string): boolean {
		return assignedUsers.some(u => u.id === userId);
	}

	let unassignedUsers = $derived(allUsers.filter(u => !isAssigned(u.id)));
</script>

<svelte:head>
	<title>Admin - Backend Management - PyPSA App</title>
</svelte:head>

<div class="space-y-6">
	<div>
		<h1 class="text-2xl font-bold">Backend Management</h1>
		<p class="text-muted-foreground">Manage Snakedispatch execution backends and user assignments</p>
	</div>

	{#if loading}
		<div class="text-muted-foreground text-sm">Loading backends...</div>
	{:else if backends.length === 0}
		<div class="rounded-md border p-6 text-center text-muted-foreground">
			<Server class="mx-auto mb-2 size-8" />
			<p>No backends configured.</p>
			<p class="text-xs mt-1">Set <code>SNAKEDISPATCH_BACKENDS</code> to register backends.</p>
		</div>
	{:else}
		<div class="rounded-md border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>Name</Table.Head>
						<Table.Head>URL</Table.Head>
						<Table.Head>Status</Table.Head>
						<Table.Head>Created</Table.Head>
						<Table.Head class="text-right">Actions</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each backends as backend}
						<Table.Row>
							<Table.Cell>
								<div class="flex items-center gap-2">
									<Server class="size-4 text-muted-foreground" />
									<span class="font-medium">{backend.name}</span>
								</div>
							</Table.Cell>
							<Table.Cell>
								<code class="text-xs">{backend.url}</code>
							</Table.Cell>
							<Table.Cell>
								<Badge variant={backend.is_active ? 'default' : 'outline'}>
									{backend.is_active ? 'active' : 'inactive'}
								</Badge>
							</Table.Cell>
							<Table.Cell>{formatDate(backend.created_at)}</Table.Cell>
							<Table.Cell class="text-right">
								<Button
									variant="ghost"
									size="sm"
									onclick={() => openUserDialog(backend)}
								>
									<Users class="mr-1 size-4" />
									Users
								</Button>
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{/if}
</div>

<!-- User Assignment Dialog -->
<Dialog.Root bind:open={dialogOpen}>
	<Dialog.Content class="max-w-md">
		{#if selectedBackend}
			<Dialog.Header>
				<Dialog.Title class="flex items-center gap-2">
					<Server class="size-5" />
					{selectedBackend.name}
				</Dialog.Title>
				<Dialog.Description>Manage user assignments for this backend.</Dialog.Description>
			</Dialog.Header>

			{#if usersLoading}
				<div class="text-muted-foreground text-sm py-4">Loading users...</div>
			{:else}
				<div class="space-y-4">
					<!-- Assigned users -->
					<div>
						<h3 class="text-sm font-medium mb-2">Assigned Users ({assignedUsers.length})</h3>
						{#if assignedUsers.length === 0}
							<p class="text-xs text-muted-foreground">No users assigned. Admins always have access.</p>
						{:else}
							<div class="space-y-1">
								{#each assignedUsers as user}
									<div class="flex items-center justify-between rounded-md border px-3 py-2">
										<span class="text-sm">{user.username}</span>
										<Button
											variant="ghost"
											size="icon"
											class="size-7"
											onclick={() => unassignUser(user.id)}
											title="Remove"
										>
											<Trash2 class="size-3.5 text-destructive" />
										</Button>
									</div>
								{/each}
							</div>
						{/if}
					</div>

					<!-- Add user -->
					{#if unassignedUsers.length > 0}
						<div>
							<h3 class="text-sm font-medium mb-2">Add User</h3>
							<div class="space-y-1 max-h-48 overflow-y-auto">
								{#each unassignedUsers as user}
									<div class="flex items-center justify-between rounded-md border px-3 py-2">
										<span class="text-sm">{user.username}</span>
										<Button
											variant="ghost"
											size="icon"
											class="size-7"
											onclick={() => assignUser(user.id)}
											title="Assign"
										>
											<Plus class="size-3.5" />
										</Button>
									</div>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/if}
		{/if}
	</Dialog.Content>
</Dialog.Root>
