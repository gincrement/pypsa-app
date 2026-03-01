<script lang="ts">
	import { onMount } from 'svelte';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import { admin } from '$lib/api/client.js';
	import { formatDate } from '$lib/utils.js';
	import { Check, Clock, User as UserIcon, Shield, Settings } from 'lucide-svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as Table from '$lib/components/ui/table';
	import * as Avatar from '$lib/components/ui/avatar';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Badge } from '$lib/components/ui/badge';
	import UsersSkeleton from './components/UsersSkeleton.svelte';
	import type { User } from '$lib/types.js';

	let users = $state<User[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let filter = $state('all');
	let selectedUser = $state<User | null>(null);
	let dialogOpen = $state(false);
	let allPermissions = $state<string[]>([]);
	let rolePermissions = $state<Record<string, string[]>>({});

	onMount(async () => {
		await Promise.all([loadUsers(), loadPermissions()]);
	});

	async function loadPermissions() {
		try {
			const response = await admin.getPermissions();
			allPermissions = response.permissions as string[];
			rolePermissions = response.role_permissions as Record<string, string[]>;
		} catch (err) {
			console.error('Failed to load permissions:', err);
		}
	}

	async function loadUsers() {
		loading = true;
		error = null;
		try {
			const role = filter === 'all' ? null : filter;
			const response = await admin.listUsers(0, 100, role);
			users = response.data;
		} catch (err) {
			error = (err as Error).message;
		} finally {
			loading = false;
		}
	}

	async function approveUser(userId: string) {
		try {
			await admin.approveUser(userId);
			await loadUsers();
		} catch (err) {
			error = (err as Error).message;
		}
	}

	async function updateRole(userId: string, newRole: string) {
		try {
			await admin.updateUserRole(userId, newRole);
			await loadUsers();
		} catch (err) {
			error = (err as Error).message;
		}
	}

	async function deleteUser(userId: string, username: string) {
		if (!confirm(`Are you sure you want to delete user "${username}"?`)) {
			return;
		}
		try {
			await admin.deleteUser(userId);
			await loadUsers();
		} catch (err) {
			error = (err as Error).message;
		}
	}

	async function handleFilterChange(newFilter: string) {
		filter = newFilter;
		await loadUsers();
	}

	function openPermissions(user: User) {
		selectedUser = user;
		dialogOpen = true;
	}

	function getRole(user: User) {
		if (!user.permissions?.length) return 'pending';
		if (user.permissions.includes('users:manage')) return 'admin';
		return 'user';
	}

	function getRoleBadgeVariant(role: string) {
		if (role === 'admin') return 'default';
		if (role === 'user') return 'secondary';
		return 'outline';
	}

</script>

<svelte:head>
	<title>Admin - User Management - PyPSA App</title>
</svelte:head>

<div class="space-y-6">
	<div>
		<h1 class="text-2xl font-bold">User Management</h1>
		<p class="text-muted-foreground">Manage user accounts and permissions</p>
	</div>

	{#if error}
		<div class="rounded-md bg-destructive/15 p-4 text-destructive">
			{error}
		</div>
	{/if}

	<div class="flex gap-2">
		<Button
			variant={filter === 'all' ? 'default' : 'outline'}
			size="sm"
			onclick={() => handleFilterChange('all')}
		>
			All Users
		</Button>
		<Button
			variant={filter === 'pending' ? 'default' : 'outline'}
			size="sm"
			onclick={() => handleFilterChange('pending')}
		>
			<Clock class="mr-1 size-4" />
			Pending
		</Button>
		<Button
			variant={filter === 'user' ? 'default' : 'outline'}
			size="sm"
			onclick={() => handleFilterChange('user')}
		>
			<UserIcon class="mr-1 size-4" />
			Users
		</Button>
		<Button
			variant={filter === 'admin' ? 'default' : 'outline'}
			size="sm"
			onclick={() => handleFilterChange('admin')}
		>
			<Shield class="mr-1 size-4" />
			Admins
		</Button>
	</div>

	{#if loading}
		<UsersSkeleton />
	{:else if users.length === 0}
		<p class="text-muted-foreground">No users found.</p>
	{:else}
		<div class="rounded-md border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>User</Table.Head>
						<Table.Head>Email</Table.Head>
						<Table.Head>Role</Table.Head>
						<Table.Head>Created</Table.Head>
						<Table.Head>Last Login</Table.Head>
						<Table.Head class="text-right">Actions</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each users as user}
						{@const userRole = getRole(user)}
						<Table.Row>
							<Table.Cell>
								<div class="flex items-center gap-2">
									<Avatar.Root class="size-8">
										<Avatar.Image class="" src={user.avatar_url} alt={user.username} />
										<Avatar.Fallback class="">
											{user.username.substring(0, 2).toUpperCase()}
										</Avatar.Fallback>
									</Avatar.Root>
									<span class="font-medium">{user.username}</span>
								</div>
							</Table.Cell>
							<Table.Cell>{user.email || '-'}</Table.Cell>
							<Table.Cell>
								<Badge variant={getRoleBadgeVariant(userRole)}>
									{userRole}
								</Badge>
							</Table.Cell>
							<Table.Cell>{formatDate(user.created_at)}</Table.Cell>
							<Table.Cell>{formatDate(user.last_login)}</Table.Cell>
							<Table.Cell class="text-right">
								<div class="flex justify-end gap-1">
									{#if userRole === 'pending'}
										<Button
											variant="ghost"
											size="icon"
											class="size-8"
											onclick={() => approveUser(user.id)}
											title="Approve"
										>
											<Check class="size-4 text-green-600" />
										</Button>
									{/if}
									<Button
										variant="ghost"
										size="icon"
										class="size-8"
										onclick={() => openPermissions(user)}
										title="Permissions"
									>
										<Settings class="size-4" />
									</Button>
								</div>
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{/if}
</div>

<Dialog.Root bind:open={dialogOpen}>
	<Dialog.Content class="max-w-xs">
		{#if selectedUser}
			{@const userRole = getRole(selectedUser)}
			<Dialog.Header>
				<Dialog.Title class="flex items-center gap-2 text-sm">
					<Avatar.Root class="size-6">
						<Avatar.Image class="" src={selectedUser.avatar_url} alt={selectedUser.username} />
						<Avatar.Fallback class="text-xs">
							{selectedUser.username.substring(0, 2).toUpperCase()}
						</Avatar.Fallback>
					</Avatar.Root>
					{selectedUser.username}
				</Dialog.Title>
			</Dialog.Header>
			<div class="space-y-3 text-xs">
				<div class="space-y-1 text-muted-foreground">
					<p>{selectedUser.email || 'No email'}</p>
					<p>Created: {formatDate(selectedUser.created_at)}</p>
					<p>Last login: {formatDate(selectedUser.last_login)}</p>
				</div>
				<div class="flex items-center justify-between">
					<span class="text-muted-foreground">Role</span>
					{#if selectedUser.id === authStore.user?.id}
						<Badge variant="outline" class="text-xs">{userRole} (you)</Badge>
					{:else}
						<select
							class="rounded border bg-background px-2 py-1 text-xs"
							value={userRole}
							onchange={(e: Event) => updateRole(selectedUser!.id, (e.target as HTMLSelectElement).value)}
						>
							<option value="admin">admin</option>
							<option value="user">user</option>
							<option value="pending">pending</option>
						</select>
					{/if}
				</div>
				<div class="space-y-1">
					<span class="text-muted-foreground">Permissions</span>
					<div class="flex flex-wrap gap-1">
						{#each allPermissions as perm}
							{@const hasPerm = selectedUser.permissions?.includes(perm)}
							<code class="rounded px-1.5 py-0.5 text-xs {hasPerm ? 'bg-muted' : 'bg-muted/30 text-muted-foreground line-through'}">{perm}</code>
						{/each}
					</div>
				</div>
				{#if selectedUser.id !== authStore.user?.id}
					<button
						class="text-destructive hover:underline"
						onclick={() => { deleteUser(selectedUser!.id, selectedUser!.username); dialogOpen = false; }}
					>
						Delete user
					</button>
				{/if}
			</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>
