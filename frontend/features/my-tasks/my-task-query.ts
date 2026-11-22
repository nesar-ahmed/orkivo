/**
 * A person's own list, as it lives in the URL:
 * `/app/my-tasks?status=all&priority=high&workspace=…&due=…&order=priority&search=…`,
 * or `?view=calendar&month=2026-11` for its calendar.
 *
 * The URL is the single source of truth, like a board's (`task-query.ts`). Two
 * defaults differ from a board, because this list answers "what should I do
 * next": it shows *open* work unless told otherwise (`status=all` shows
 * everything), and it is sorted by due date. Neither default is written to the
 * URL, so the plain address always means the useful view.
 */

import { DUE_FILTERS, parseMonth, type DueFilter, type MonthKey } from "@/features/tasks/task-dates";
import { parsePageParam } from "@/lib/utils/page-param";
import type { TaskPriority, TaskStatusFilter } from "@/types/task";

export const MY_TASKS_PATH = "/app/my-tasks";

export type MyTaskView = "list" | "calendar";

/** `all` is the one value the board does not need: its default is already "all". */
export type MyTaskStatusFilter = TaskStatusFilter | "all";

/** The orders a person's own list offers. */
export type MyTaskOrder = "due" | "priority" | "newest";

export interface MyTaskQuery {
  readonly view: MyTaskView;
  readonly search?: string;
  /** Defaults to `open`. */
  readonly status: MyTaskStatusFilter;
  readonly priority?: TaskPriority;
  /** One of the viewer's workspaces, by id. */
  readonly workspace?: string;
  /** List only: where the due date falls, on the viewer's own day. */
  readonly due?: DueFilter;
  /** List only. Defaults to `due`. */
  readonly order: MyTaskOrder;
  /** Calendar only: the month shown. Absent means the current one. */
  readonly month?: MonthKey;
  readonly page: number;
}

const STATUSES: readonly MyTaskStatusFilter[] = ["open", "all", "todo", "in_progress", "done"];
const PRIORITIES: readonly TaskPriority[] = ["low", "medium", "high"];
const ORDERS: readonly MyTaskOrder[] = ["due", "priority", "newest"];
const MAX_SEARCH = 200;
/** A workspace id as the API spells it. Anything else would only earn a 422. */
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type RawParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export function parseMyTaskQuery(params: RawParams): MyTaskQuery {
  const view: MyTaskView = first(params.view) === "calendar" ? "calendar" : "list";
  const workspace = first(params.workspace)?.trim().toLowerCase();
  return {
    view,
    search: first(params.search)?.trim().slice(0, MAX_SEARCH) || undefined,
    status: STATUSES.find((value) => value === first(params.status)) ?? "open",
    priority: PRIORITIES.find((value) => value === first(params.priority)),
    workspace: workspace && UUID_PATTERN.test(workspace) ? workspace : undefined,
    due: view === "list" ? DUE_FILTERS.find((value) => value === first(params.due)) : undefined,
    order: ORDERS.find((value) => value === first(params.order)) ?? "due",
    month: view === "calendar" ? parseMonth(first(params.month)) : undefined,
    page: view === "list" ? parsePageParam(first(params.page)) : 1,
  };
}

/** Whether anything narrows the list beyond its defaults. */
export function isFiltered(query: MyTaskQuery): boolean {
  return Boolean(
    query.search || query.status !== "open" || query.priority || query.workspace || query.due,
  );
}

/** The same query back at its defaults, keeping the view, order and month. */
export const NO_FILTERS: Partial<MyTaskQuery> = {
  search: undefined,
  status: "open",
  priority: undefined,
  workspace: undefined,
  due: undefined,
};

/** The status to ask the API for: `all` means no status filter at all. */
export function apiStatus(status: MyTaskStatusFilter): TaskStatusFilter | undefined {
  return status === "all" ? undefined : status;
}

/**
 * The URL for `query` with `changes` applied. Changing a filter or the view goes
 * back to page 1, since the old page number no longer means anything.
 */
export function myTaskQueryHref(query: MyTaskQuery, changes: Partial<MyTaskQuery> = {}): string {
  const next = { ...query, ...changes };
  const resetsPage = Object.keys(changes).some((key) => key !== "page");
  const params = new URLSearchParams();
  if (next.view === "calendar") params.set("view", "calendar");
  if (next.view === "calendar" && next.month) params.set("month", next.month);
  if (next.search) params.set("search", next.search);
  if (next.status !== "open") params.set("status", next.status);
  if (next.priority) params.set("priority", next.priority);
  if (next.workspace) params.set("workspace", next.workspace);
  if (next.view === "list" && next.due) params.set("due", next.due);
  if (next.view === "list" && next.order !== "due") params.set("order", next.order);
  const page = resetsPage ? 1 : next.page;
  if (next.view === "list" && page > 1) params.set("page", String(page));
  const suffix = params.toString();
  return suffix ? `${MY_TASKS_PATH}?${suffix}` : MY_TASKS_PATH;
}
