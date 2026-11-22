import { ListTodo, SearchX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button-link";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination } from "@/components/ui/pagination";
import type { MyTaskViewData } from "@/features/my-tasks/api/my-task-view-data";
import { MyTaskList } from "@/features/my-tasks/components/my-task-list";
import { MyTasksToolbar } from "@/features/my-tasks/components/my-tasks-toolbar";
import {
  MY_TASKS_PATH,
  NO_FILTERS,
  isFiltered,
  myTaskQueryHref,
  type MyTaskQuery,
} from "@/features/my-tasks/my-task-query";
import { QuickAdd } from "@/features/tasks/components/quick-add";
import { TaskCalendar } from "@/features/tasks/components/task-calendar";
import { shiftMonth } from "@/features/tasks/task-dates";
import type { TaskChoices } from "@/features/tasks/task-utils";
import { hasCapability, workspacePath } from "@/features/workspaces/workspace-utils";
import type { Workspace } from "@/types/workspace";

/**
 * A person's own work, from every workspace they are in: what is assigned to
 * them, plus their private to-dos. A list sorted by due date and grouped into
 * "overdue", "today", "next 7 days" and "later", or a calendar.
 *
 * Quick add writes to the private workspace --- the one place a new task is theirs
 * without assigning it --- and is hidden while the list is narrowed to a company,
 * where a private task would vanish from view the moment it was added.
 */
export function MyTasksScreen({
  query,
  data,
  workspaces,
  personal,
  choices,
}: {
  query: MyTaskQuery;
  data: MyTaskViewData;
  workspaces: readonly Workspace[];
  personal: Workspace | null;
  /** The private workspace's people, projects and labels, for tasks added here. */
  choices: TaskChoices;
}) {
  const canAdd =
    personal !== null &&
    hasCapability(personal, "edit_content") &&
    (!query.workspace || query.workspace === personal.id);
  const calendar = data.calendar;

  const empty = isFiltered(query) ? (
    <EmptyState
      icon={<SearchX />}
      title="No tasks match these filters"
      description="Try another search term, or clear the filters to see all your open work."
    >
      <ButtonLink href={myTaskQueryHref(query, NO_FILTERS)}>Clear filters</ButtonLink>
    </EmptyState>
  ) : (
    <EmptyState
      icon={<ListTodo />}
      title="Nothing on your plate"
      description="Tasks assigned to you in any workspace show up here, next to your private to-dos."
    />
  );

  return (
    <section aria-labelledby="my-tasks-heading" className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h1 id="my-tasks-heading" className="text-xl font-semibold tracking-tight">
            My tasks
          </h1>
          {data.list ? <Badge variant="neutral">{data.list.total}</Badge> : null}
        </div>
        <p className="text-sm text-muted-foreground">
          Everything assigned to you, in every workspace you are in, with your private to-dos.
        </p>
      </header>

      <MyTasksToolbar query={query} workspaces={workspaces} />

      {canAdd && personal ? (
        <QuickAdd
          workspaceId={personal.id}
          shared={false}
          basePath={workspacePath(personal, "tasks")}
          choices={choices}
        />
      ) : null}

      {data.loadError ? (
        <div
          role="alert"
          className="rounded-xl border border-danger/30 bg-danger/10 p-5 text-sm text-danger"
        >
          <p className="font-medium">Your tasks could not be loaded.</p>
          <p className="mt-1 text-xs">{data.loadError}</p>
          <ButtonLink href={myTaskQueryHref(query)} className="mt-3">
            Retry
          </ButtonLink>
        </div>
      ) : calendar ? (
        <TaskCalendar
          data={calendar}
          scope={{ kind: "mine", workspaces, personal, choices }}
          previousHref={myTaskQueryHref(query, { month: shiftMonth(calendar.month, -1) })}
          nextHref={myTaskQueryHref(query, { month: shiftMonth(calendar.month, 1) })}
          todayHref={myTaskQueryHref(query, { month: undefined })}
        />
      ) : data.list ? (
        <div className="flex flex-col gap-4">
          <MyTaskList
            tasks={data.list.items}
            workspaces={workspaces}
            grouped={query.order === "due"}
            empty={empty}
          />
          <Pagination
            page={data.list.page}
            pages={data.list.pages}
            total={data.list.total}
            basePath={MY_TASKS_PATH}
            noun="tasks"
            params={{
              search: query.search,
              status: query.status === "open" ? undefined : query.status,
              priority: query.priority,
              workspace: query.workspace,
              due: query.due,
              order: query.order === "due" ? undefined : query.order,
            }}
          />
        </div>
      ) : null}
    </section>
  );
}
