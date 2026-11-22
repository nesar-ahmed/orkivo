import Link from "next/link";
import { Pencil, Tags } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { DeleteLabelButton } from "@/features/labels/components/delete-label-button";
import { LabelChip } from "@/features/labels/components/label-chip";
import { LabelFormDialog } from "@/features/labels/components/label-form-dialog";
import { LABEL_COLOR_NAMES, labelTasksHref } from "@/features/labels/label-utils";
import { formatAccountDate } from "@/features/users/user-utils";
import { hasCapability, isShared, readOnlyReason } from "@/features/workspaces/workspace-utils";
import type { LabelSummary } from "@/types/label";
import type { Workspace } from "@/types/workspace";

/**
 * A workspace's labels: how each looks, how many tasks carry it, and who made it.
 *
 * Which controls appear follows the workspace's `capabilities` from the backend's
 * access policy: `manage_labels` (owners, admins and managers) to rename and recolor,
 * `manage` (owners and admins) to delete. For members and viewers, and in view
 * mode (a suspended company), neither is present, so the table is read-only
 * without restating that rule here. Each action is still
 * authorized per request (architecture doc 8.2).
 */
export function LabelTable({
  workspace,
  labels,
}: {
  workspace: Workspace;
  labels: readonly LabelSummary[];
}) {
  const canEdit = hasCapability(workspace, "manage_labels");
  const canDelete = hasCapability(workspace, "manage");
  const shared = isShared(workspace.kind);

  if (labels.length === 0) {
    return (
      <EmptyState
        icon={<Tags />}
        title="No labels yet"
        description={
          canEdit
            ? "Tag tasks by type, area or customer, then filter the board by any label."
            : readOnlyReason(workspace) === "suspended"
              ? "There are no labels here, and this workspace is in view mode."
              : "There are no labels here yet."
        }
      />
    );
  }

  return (
    // `relative`: see MemberTable --- it keeps screen-reader-only text inside the
    // scroll container on narrow screens.
    <div className="relative overflow-x-auto rounded-xl border border-border bg-card shadow-xs">
      <table className="w-full min-w-[32rem] text-left text-sm">
        <caption className="sr-only">
          Labels in this workspace, how many tasks carry each, and who created them.
        </caption>
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-3 font-medium">
              Label
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Tasks
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Created
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {labels.map((label) => (
            <tr key={label.id}>
              <th scope="row" className="px-4 py-3 font-normal">
                <span className="flex items-center gap-2">
                  <LabelChip label={label} className="max-w-60 text-xs" />
                  <span className="sr-only">, {LABEL_COLOR_NAMES[label.color]}</span>
                </span>
              </th>
              <td className="px-4 py-3 text-xs whitespace-nowrap text-muted-foreground">
                <Link
                  href={labelTasksHref(workspace, label.id)}
                  className="hover:text-primary"
                  aria-label={`${label.task_count} ${label.task_count === 1 ? "task" : "tasks"} labelled ${label.name}`}
                >
                  <span className="font-medium text-foreground">{label.task_count}</span>{" "}
                  {label.task_count === 1 ? "task" : "tasks"}
                </Link>
              </td>
              <td className="px-4 py-3 text-xs text-muted-foreground">
                <span className="block text-foreground">
                  {label.created_by?.display_name ?? "A former member"}
                </span>
                {formatAccountDate(label.created_at)}
              </td>
              <td className="px-4 py-3 text-right">
                <div className="flex justify-end gap-1">
                  {canEdit ? (
                    <LabelFormDialog
                      workspaceId={workspace.id}
                      label={label}
                      shared={shared}
                      trigger={
                        <Button variant="ghost" size="icon-sm" aria-label={`Edit ${label.name}`}>
                          <Pencil aria-hidden="true" />
                        </Button>
                      }
                    />
                  ) : null}
                  {canDelete ? <DeleteLabelButton label={label} /> : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
