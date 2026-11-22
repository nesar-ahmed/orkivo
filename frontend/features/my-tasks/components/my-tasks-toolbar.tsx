"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowUpDown,
  CalendarClock,
  CalendarDays,
  CalendarX,
  List,
  ListChecks,
  X,
} from "lucide-react";
import { buttonClasses } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  NO_FILTERS,
  isFiltered,
  myTaskQueryHref,
  type MyTaskOrder,
  type MyTaskQuery,
  type MyTaskStatusFilter,
} from "@/features/my-tasks/my-task-query";
import { PriorityIcon } from "@/features/tasks/components/task-icons";
import {
  DUE_FILTERS,
  DUE_FILTER_LABELS,
  type DueFilter,
} from "@/features/tasks/task-dates";
import { statusFilterIcon } from "@/features/tasks/components/task-toolbar";
import {
  FilterMenu,
  SearchBox,
  ViewSwitch,
} from "@/features/tasks/components/toolbar-controls";
import { PRIORITY_LABELS, STATUS_FILTER_LABELS } from "@/features/tasks/task-utils";
import { WorkspaceMark } from "@/features/workspaces/components/workspace-switcher";
import type { TaskPriority } from "@/types/task";
import type { Workspace } from "@/types/workspace";

/** Open first (the default), then everything, then one status at a time. */
const STATUS_OPTIONS: readonly Exclude<MyTaskStatusFilter, "open">[] = [
  "all",
  "todo",
  "in_progress",
  "done",
];

const ORDER_LABELS: Record<MyTaskOrder, string> = {
  due: "Due date",
  priority: "Priority",
  newest: "Newest",
};

/**
 * View switch, order, search and filters for a person's own list. Like a board's
 * toolbar, everything is written to the URL: search replaces the history entry,
 * the rest pushes, so Back undoes a filter. "Open" is the default status, so the
 * status filter offers the others --- "all" included --- and "Clear filters"
 * comes back to open work.
 */
export function MyTasksToolbar({
  query,
  workspaces,
}: {
  query: MyTaskQuery;
  workspaces: readonly Workspace[];
}) {
  const router = useRouter();
  const go = (changes: Partial<MyTaskQuery>) =>
    router.push(myTaskQueryHref(query, changes), { scroll: false });

  const byId = new Map(workspaces.map((workspace) => [workspace.id, workspace]));
  const workspaceNames: Record<string, string> = {};
  for (const workspace of workspaces) {
    workspaceNames[workspace.id] = workspace.kind === "personal" ? "Private" : workspace.name;
  }
  if (query.workspace && !(query.workspace in workspaceNames)) {
    workspaceNames[query.workspace] = "A workspace you left";
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <ViewSwitch
        options={[
          {
            href: myTaskQueryHref(query, { view: "list" }),
            active: query.view === "list",
            icon: <List aria-hidden="true" />,
            label: "List",
          },
          {
            href: myTaskQueryHref(query, { view: "calendar" }),
            active: query.view === "calendar",
            icon: <CalendarDays aria-hidden="true" />,
            label: "Calendar",
          },
        ]}
      />
      {query.view === "list" ? (
        <OrderMenu value={query.order} onChange={(order) => go({ order })} />
      ) : null}

      <SearchBox
        id="my-task-search"
        value={query.search}
        hrefFor={(search) => myTaskQueryHref(query, { search })}
        placeholder="Search my tasks…"
      />

      <FilterMenu<Exclude<MyTaskStatusFilter, "open">>
        label="Status"
        value={query.status === "open" ? undefined : query.status}
        options={STATUS_OPTIONS}
        labels={{ all: "All, including done", ...STATUS_FILTER_LABELS }}
        icon={(value) =>
          value === "all" ? <ListChecks aria-hidden="true" /> : statusFilterIcon(value)
        }
        anyLabel={STATUS_FILTER_LABELS.open}
        onChange={(status) => go({ status: status ?? "open" })}
      />
      <FilterMenu<TaskPriority>
        label="Priority"
        value={query.priority}
        options={["high", "medium", "low"]}
        labels={PRIORITY_LABELS}
        icon={(value) => <PriorityIcon priority={value} />}
        onChange={(priority) => go({ priority })}
      />
      {query.view === "list" ? (
        <FilterMenu<DueFilter>
          label="Due"
          value={query.due}
          options={DUE_FILTERS}
          labels={DUE_FILTER_LABELS}
          icon={(value) =>
            value === "none" ? <CalendarX aria-hidden="true" /> : <CalendarClock aria-hidden="true" />
          }
          onChange={(due) => go({ due })}
          anyLabel="Any due date"
        />
      ) : null}
      {workspaces.length > 1 || query.workspace ? (
        <FilterMenu<string>
          label="Workspace"
          value={query.workspace}
          options={workspaces.map((workspace) => workspace.id)}
          labels={workspaceNames}
          icon={(id) => (
            <WorkspaceMark workspace={byId.get(id) ?? null} className="size-4 rounded text-[0.6rem]" />
          )}
          onChange={(workspace) => go({ workspace })}
          contentClassName="max-h-80 w-56 overflow-y-auto"
        />
      ) : null}

      {isFiltered(query) ? (
        <Link href={myTaskQueryHref(query, NO_FILTERS)} className={buttonClasses("ghost", "sm")}>
          <X aria-hidden="true" />
          Clear filters
        </Link>
      ) : null}
    </div>
  );
}

/** How the list is sorted. Not a filter: it hides nothing, so "Clear filters" keeps it. */
function OrderMenu({
  value,
  onChange,
}: {
  value: MyTaskOrder;
  onChange: (value: MyTaskOrder) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className={buttonClasses("secondary", "sm")}>
        <ArrowUpDown aria-hidden="true" />
        Sort: {ORDER_LABELS[value]}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-48">
        <DropdownMenuLabel>Sort tasks by</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={value}
          onValueChange={(next) => onChange(next as MyTaskOrder)}
        >
          {(Object.keys(ORDER_LABELS) as MyTaskOrder[]).map((order) => (
            <DropdownMenuRadioItem key={order} value={order}>
              {ORDER_LABELS[order]}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
