import { ClipboardList, Lock, SearchX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button-link";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination } from "@/components/ui/pagination";
import type { TaskViewData } from "@/features/tasks/api/task-view-data";
import { QuickAdd } from "@/features/tasks/components/quick-add";
import { TaskBoardView } from "@/features/tasks/components/task-board-view";
import { TaskCalendar } from "@/features/tasks/components/task-calendar";
import { TaskListView } from "@/features/tasks/components/task-list-view";
import { TaskToolbar } from "@/features/tasks/components/task-toolbar";
import {
  NO_FILTERS,
  isFiltered,
  taskQueryHref,
  type TaskQuery,
} from "@/features/tasks/task-query";
import { shiftMonth } from "@/features/tasks/task-dates";
import { defaultsFor, type TaskChoices } from "@/features/tasks/task-utils";
import {
  WORKSPACE_ROLE_LABELS,
  hasCapability,
  isShared,
  readOnlyReason,
  workspacePath,
} from "@/features/workspaces/workspace-utils";
import type { Workspace } from "@/types/workspace";

/**
 * One workspace's tasks: toolbar, quick add, and the list, the board or the
 * calendar.
 *
 * The same screen serves the private workspace and every company; what differs
 * is what the backend says the caller may do there. Adding tasks takes the
 * workspace's `edit_content` (a viewer, or anyone in a suspended company, has
 * none); changing one takes that task's own `capabilities`. Without them the
 * screen renders read-only rather than offering controls the API would refuse
 * (architecture doc 8.2/8.3).
 *
 * `choices` (the workspace's people, projects and labels) feeds the filters,
 * pickers and the board's project lanes. While the view is filtered to one
 * person, project or label, tasks created from it start with it.
 */
export function TaskBoard({
  workspace,
  query,
  data,
  choices,
}: {
  workspace: Workspace;
  query: TaskQuery;
  data: TaskViewData;
  choices: TaskChoices;
}) {
  const canCreate = hasCapability(workspace, "edit_content");
  const defaults = defaultsFor(query, choices.assignees.viewerId);
  const grouped = query.group === "project";
  const shared = isShared(workspace.kind);
  const basePath = workspacePath(workspace, "tasks");
  // The calendar says how many tasks fall due in its own header.
  const total =
    data.list?.total ?? data.columns?.reduce((sum, column) => sum + column.total, 0) ?? null;
  const calendar = data.calendar;

  const empty = isFiltered(query) ? (
    <EmptyState
      icon={<SearchX />}
      title="No tasks match these filters"
      description="Try another search term, or clear the filters to see everything."
    >
      <ButtonLink href={taskQueryHref(basePath, query, NO_FILTERS)}>
        Clear filters
      </ButtonLink>
    </EmptyState>
  ) : (
    <EmptyState
      icon={<ClipboardList />}
      title="No tasks yet"
      description={
        canCreate
          ? shared
            ? "Add the first task above. Everyone in this company will see it."
            : "Add your first task above. Only you can see what you put here."
          : readOnlyReason(workspace) === "suspended"
            ? "There is nothing here yet, and this workspace is in view mode."
            : "There is nothing here yet. Tasks added by others will appear here."
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
        canCreate={canCreate}
        workspaceId={workspace.id}
        shared={shared}
        choices={choices}
        defaults={defaults}
      />

      {canCreate ? (
        <QuickAdd
          workspaceId={workspace.id}
          shared={shared}
          basePath={basePath}
          choices={choices}
          defaults={defaults}
        />
      ) : (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Lock aria-hidden="true" className="size-4" />
          {readOnlyReason(workspace) === "suspended"
            ? "View mode: tasks can be opened and read, but not added or changed."
            : `As a ${WORKSPACE_ROLE_LABELS[workspace.my_role].toLowerCase()}, you can open and read tasks, but not add or change them.`}
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
      ) : calendar ? (
        <TaskCalendar
          data={calendar}
          scope={{
            kind: "workspace",
            workspaceId: workspace.id,
            basePath,
            canCreate,
            shared,
            choices,
            defaults,
          }}
          previousHref={taskQueryHref(basePath, query, { month: shiftMonth(calendar.month, -1) })}
          nextHref={taskQueryHref(basePath, query, { month: shiftMonth(calendar.month, 1) })}
          todayHref={taskQueryHref(basePath, query, { month: undefined })}
        />
      ) : data.columns ? (
        <TaskBoardView
          columns={data.columns}
          canCreate={canCreate}
          basePath={basePath}
          workspaceId={workspace.id}
          shared={shared}
          choices={choices}
          defaults={defaults}
          grouped={grouped}
          projectFilter={query.project}
          listHref={taskQueryHref(basePath, query, { view: "list" })}
        />
      ) : data.list ? (
        <div className="flex flex-col gap-4">
          <TaskListView
            tasks={data.list.items}
            basePath={basePath}
            empty={empty}
            projects={choices.projects}
            labels={choices.labels}
            grouped={grouped}
            continuesGroup={data.continuesGroup}
            bulk={canCreate ? { workspaceId: workspace.id, choices } : undefined}
          />
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
              assignee: query.assignee,
              project: query.project,
              label: query.label,
              due: query.due,
              group: query.group,
            }}
          />
        </div>
      ) : null}
    </section>
  );
}
