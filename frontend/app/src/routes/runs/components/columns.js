import { renderComponent } from '$lib/components/ui/data-table/render-helpers.js';
import { formatDuration } from '$lib/utils.js';
import StatusCell from '../cells/status-cell.svelte';
import ActionsCell from '$lib/components/cells/ActionsCell.svelte';
import { X, Trash2 } from 'lucide-svelte';
import OwnerCell from '$lib/components/OwnerCell.svelte';

export const createColumns = (helpers) => {
	const {
		formatRelativeTime,
		handleCancel,
		handleRemove,
		authEnabled,
		getCancellingId = () => null,
		getRemovingId = () => null
	} = helpers;

	return [
		{
			accessorKey: 'status',
			header: 'Status',
			enableSorting: true,
			cell: (info) => {
				const run = info.row.original;
				return renderComponent(StatusCell, { run });
			}
		},
		{
			accessorKey: 'workflow',
			header: 'Workflow',
			enableSorting: true,
			sortingFn: 'alphanumeric',
			cell: (info) => {
				const run = info.row.original;
				let source = run.workflow || '';

				// Strip URL prefixes
				if (source.startsWith('https://github.com/')) {
					source = source.replace('https://github.com/', '');
				} else if (source.startsWith('https://')) {
					source = source.replace('https://', '');
				} else if (source.startsWith('http://')) {
					source = source.replace('http://', '');
				}
				// Strip trailing .git
				source = source.replace(/\.git$/, '');

				// Append git ref/sha
				const ref = run.git_ref;
				const sha = run.git_sha ? run.git_sha.slice(0, 8) : null;
				if (ref && sha) {
					source += ` ${ref}@${sha}`;
				} else if (sha) {
					source += ` @${sha}`;
				} else if (ref) {
					source += ` ${ref}`;
				}

				return source;
			}
		},
		{
			accessorKey: 'configfile',
			header: 'Config',
			enableSorting: true,
			sortingFn: 'alphanumeric',
			cell: (info) => {
				return info.getValue() || '\u2014';
			}
		},
		{
			id: 'duration',
			header: 'Duration',
			enableSorting: false,
			cell: (info) => {
				const run = info.row.original;
				return formatDuration(run.started_at, run.completed_at) ?? '\u2014';
			}
		},
		{
			accessorKey: 'created_at',
			header: 'Created',
			enableSorting: true,
			sortingFn: (rowA, rowB) => {
				const a = new Date(rowA.original.created_at).getTime();
				const b = new Date(rowB.original.created_at).getTime();
				return a - b;
			},
			cell: (info) => {
				return formatRelativeTime(info.getValue());
			}
		},
		// Only shown when auth is enabled
		...(authEnabled
			? [
					{
						accessorKey: 'owner',
						header: 'Owner',
						enableSorting: false,
						cell: (info) => {
							const run = info.row.original;
							return renderComponent(OwnerCell, { item: run });
						}
					}
				]
			: []),
		{
			id: 'actions',
			header: '',
			enableSorting: false,
			cell: (info) => {
				const run = info.row.original;
				const isTerminal = ['COMPLETED', 'FAILED', 'CANCELLED'].includes(run.status);
				const isCancelling = getCancellingId() === run.id;
				const isRemoving = getRemovingId() === run.id;
				const actions = [];
				if (!isTerminal) {
					actions.push({
						icon: X,
						label: 'Cancel',
						onclick: () => handleCancel(run.id),
						loading: isCancelling
					});
				}
				actions.push({
					icon: Trash2,
					label: 'Remove',
					onclick: () => handleRemove(run.id),
					loading: isRemoving,
					variant: 'destructive'
				});
				return renderComponent(ActionsCell, { actions });
			}
		}
	];
};
