import { ClipboardList, Lock, SearchX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button-link";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination } from "@/components/ui/pagination";
import type { TaskViewData } from "@/features/tasks/api/task-view-data";
import { QuickAdd } from "@/features/tasks/components/quick-add";
import { TaskBoardView } from "@/features/tasks/components/task-board-view";
import { TaskListView } from "@/features/tasks/components/task-list-view";
import { TaskToolbar } from "@/features/tasks/components/task-toolbar";
import { isFiltered, taskQueryHref, type TaskQuery } from "@/features/tasks/task-query";
import { hasCapability, isShared, workspacePath } from "@/features/workspaces/workspace-utils";
import type { Workspace } from "@/types/workspace";

/**
 * One workspace's tasks: toolbar, quick add, and the list or the board.
 *
 * The same screen serves the private workspace and every company; what differs
 * is what the backend says the caller may do there. Without `edit_content` (a
 * suspended company, today) everything renders read-only rather than offering
 * controls the API would refuse (architecture doc 8.2/8.3).
 */
export function TaskBoard({
  workspace,
  query,
  data,
}: {
  workspace: Workspace;
  query: TaskQuery;
  data: TaskViewData;
}) {
  const canEdit = hasCapability(workspace, "edit_content");
  const shared = isShared(workspace.kind);
  const basePath = workspacePath(workspace, "tasks");
  const total =
    data.list?.total ?? data.columns?.reduce((sum, column) => sum + column.total, 0) ?? null;

  const empty = isFiltered(query) ? (
    <EmptyState
      icon={<SearchX />}
      title="No tasks match these filters"
      description="Try another search term, or clear the filters to see everything."
    >
      <ButtonLink
        href={taskQueryHref(basePath, query, { search: undefined, status: undefined, priority: undefined })}
      >
        Clear filters
      </ButtonLink>
    </EmptyState>
  ) : (
    <EmptyState
      icon={<ClipboardList />}
      title="No tasks yet"
      description={
        canEdit
          ? shared
            ? "Add the first task above. Everyone in this company will see it."
            : "Add your first task above. Only you can see what you put here."
          : "There is nothing here yet, and this workspace is in view mode."
      }
    />
  );

  return (
    <section aria-labelledby="tasks-heading" className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <h2 id="tasks-heading" className="text-lg font-semibold tracking-tight">
          Tasks
        </h2>
        {total !== null ? <Badge variant="neutral">{total}</Badge> : null}
      </div>

      <TaskToolbar
        basePath={basePath}
        query={query}
        canEdit={canEdit}
        workspaceId={workspace.id}
        shared={shared}
      />

      {canEdit ? (
        <QuickAdd workspaceId={workspace.id} shared={shared} basePath={basePath} />
      ) : (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Lock aria-hidden="true" className="size-4" />
          View mode: tasks can be opened and read, but not added or changed.
        </p>
      )}

      {data.loadError ? (
        <div
          role="alert"
          className="rounded-xl border border-danger/30 bg-danger/10 p-5 text-sm text-danger"
        >
          <p className="font-medium">Tasks could not be loaded.</p>
          <p className="mt-1 text-xs">{data.loadError}</p>
          <ButtonLink href={taskQueryHref(basePath, query)} className="mt-3">
            Retry
          </ButtonLink>
        </div>
      ) : data.columns ? (
        <TaskBoardView
          columns={data.columns}
          canEdit={canEdit}
          basePath={basePath}
          workspaceId={workspace.id}
          shared={shared}
        />
      ) : data.list ? (
        <div className="flex flex-col gap-4">
          <TaskListView tasks={data.list.items} canEdit={canEdit} basePath={basePath} empty={empty} />
          <Pagination
            page={data.list.page}
            pages={data.list.pages}
            total={data.list.total}
            basePath={basePath}
            noun="tasks"
            params={{
              search: query.search,
              status: query.status,
              priority: query.priority,
            }}
          />
        </div>
      ) : null}
    </section>
  );
}
