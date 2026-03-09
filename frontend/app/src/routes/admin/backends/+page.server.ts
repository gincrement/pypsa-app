import { getUser, requireAdmin } from '$lib/server/auth.js';
import type { PageServerLoad } from './$types.js';

export const load: PageServerLoad = async ({ cookies, fetch }) => {
	const user = await getUser(cookies, fetch);
	return { user: requireAdmin(user) };
};
