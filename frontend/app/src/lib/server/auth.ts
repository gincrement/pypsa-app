import { redirect } from '@sveltejs/kit';
import type { Cookies } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { User } from '$lib/types.js';

const backendUrl = env.BACKEND_URL || 'http://localhost:8000';

export async function getUser(cookies: Cookies, fetch: typeof globalThis.fetch): Promise<User | null> {
	const session = cookies.get('pypsa_session');
	if (!session) return null;

	try {
		const res = await fetch(`${backendUrl}/api/v1/auth/me`, {
			headers: { Cookie: `pypsa_session=${session}` }
		});
		if (!res.ok) {
			console.error(`Auth check failed: ${res.status} ${res.statusText}`);
			return null;
		}
		return await res.json();
	} catch (error) {
		const err = error as Error;
		console.error('Failed to verify authentication:', err.message, {
			backendUrl,
			errorType: err.name
		});
		return null;
	}
}

function isPending(user: User): boolean {
	return !user.permissions || user.permissions.length === 0;
}

function isAdmin(user: User): boolean {
	return user.permissions?.includes('users:manage') ?? false;
}

export function requireAuth(user: User | null): User {
	if (!user) throw redirect(302, '/login');
	if (isPending(user)) throw redirect(302, '/pending-approval');
	return user;
}

export function requireAdmin(user: User | null): User {
	const authedUser = requireAuth(user);
	if (!isAdmin(authedUser)) throw redirect(302, '/');
	return authedUser;
}
