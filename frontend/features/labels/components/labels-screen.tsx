import { Lock, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import { LabelFormDialog } from "@/features/labels/components/label-form-dialog";
import { LabelTable } from "@/features/labels/components/label-table";
import {
  hasCapability,
  isShared,
  readOnlyReason,
  workspacePath,
} from "@/features/workspaces/workspace-utils";
import type { LabelListResponse } from "@/types/label";
import type { Workspace } from "@/types/workspace";

/**
 * One workspace's labels: the list, and creating a new one.
 *
 * The same screen serves the private workspace and every company, like projects.
 * What differs is what the backend says the caller may do there: without
 * `manage_labels` (members and viewers, or anyone in view mode) nothing can be
 * added or changed.
 */
export function LabelsScreen({
  workspace,
  labels,
}: {
  workspace: Workspace;
  labels: LabelListResponse;
}) {
  const canEdit = hasCapability(workspace, "manage_labels");

  return (
    <section aria-labelledby="labels-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="labels-heading" className="text-lg font-semibold tracking-tight">
          Labels
        </h2>
        <Badge variant="neutral">{labels.total}</Badge>
        {canEdit ? (
          <div className="ml-auto">
            <LabelFormDialog
              workspaceId={workspace.id}
              shared={isShared(workspace.kind)}
              trigger={
                <Button size="sm">
                  <Plus aria-hidden="true" />
                  New label
                </Button>
              }
            />
          </div>
        ) : null}
      </div>

      {canEdit ? null : (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Lock aria-hidden="true" className="size-4" />
          {readOnlyReason(workspace) === "suspended"
            ? "View mode: labels can be read, but not added or changed."
            : "Your role lets you read labels and use them on tasks, but not add or change them."}
        </p>
      )}

      <LabelTable workspace={workspace} labels={labels.items} />
      <Pagination
        page={labels.page}
        pages={labels.pages}
        total={labels.total}
        basePath={workspacePath(workspace, "labels")}
        noun="labels"
      />
    </section>
  );
}
