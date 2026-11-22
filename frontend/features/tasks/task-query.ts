/**
 * A board's state, as it lives in the URL:
 * `?view=board&group=project&priority=high&assignee=me&project=…&label=…&due=…&search=…`,
 * or `?view=calendar&month=2026-11&status=open…` for its calendar.
 *
 * The URL is the single source of truth, so a filtered view can be shared,
 * bookmarked and restored with the back button. Anything unrecognised in the
 * query string is ignored rather than sent to the API.
 */

import {
  DUE_FILTERS,
  parseMonth,
  type DueFilter,
  type MonthKey,
} from "@/features/tasks/task-dates";
import { parsePageParam } from "@/lib/utils/page-param";
import type {
  TaskAssigneeFilter,
  TaskLabelFilter,
  TaskPriority,
  TaskProjectFilter,
  TaskStatusFilter,
} from "@/types/task";

export type TaskView = "list" | "board" | "calendar";

/** How a view is split into groups: by project, or (when absent) not at all. */
export type TaskGrouping = "project";

export interface TaskQuery {
  readonly view: TaskView;
  readonly search?: string;
  /** List and calendar: the board already splits by status. `open` is "not done". */
  readonly status?: TaskStatusFilter;
  readonly priority?: TaskPriority;
  /** A member's id, `me` or `none`; the backend resolves `me` to the viewer. */
  readonly assignee?: TaskAssigneeFilter;
  /** A project's id, or `none` for tasks outside every project. */
  readonly project?: TaskProjectFilter;
  /** A label's id, or `none` for tasks carrying no label. */
  readonly label?: TaskLabelFilter;
  /**
   * List and board: where the due date falls, on the viewer's own day. The
   * calendar is already laid out by due date, so it does not take one.
   */
  readonly due?: DueFilter;
  /** Sections in the list, swimlanes on the board. Not a filter: it hides nothing. */
  readonly group?: TaskGrouping;
  /** Calendar only: the month shown. Absent means the current one. */
  readonly month?: MonthKey;
  readonly page: number;
}

const VIEWS: readonly TaskView[] = ["list", "board", "calendar"];
const STATUSES: readonly TaskStatusFilter[] = ["open", "todo", "in_progress", "done"];
const PRIORITIES: readonly TaskPriority[] = ["low", "medium", "high"];
const MAX_SEARCH = 200;
const ASSIGNEE_KEYWORDS: readonly TaskAssigneeFilter[] = ["me", "none"];
/** A member id as the API spells it. Anything else would only earn a 422. */
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type RawParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export function parseTaskQuery(params: RawParams): TaskQuery {
  const view: TaskView = VIEWS.find((value) => value === first(params.view)) ?? "list";
  const search = first(params.search)?.trim().slice(0, MAX_SEARCH) || undefined;
  const status = STATUSES.find((value) => value === first(params.status));
  const priority = PRIORITIES.find((value) => value === first(params.priority));
  return {
    view,
    search,
    status: view !== "board" ? status : undefined,
    priority,
    assignee: parseAssignee(first(params.assignee)),
    project: parseProject(first(params.project)),
    label: parseLabel(first(params.label)),
    due:
      view !== "calendar" ? DUE_FILTERS.find((value) => value === first(params.due)) : undefined,
    group: first(params.group) === "project" && view !== "calendar" ? "project" : undefined,
    month: view === "calendar" ? parseMonth(first(params.month)) : undefined,
    page: view === "list" ? parsePageParam(first(params.page)) : 1,
  };
}

function parseAssignee(raw: string | undefined): TaskAssigneeFilter | undefined {
  const value = raw?.trim().toLowerCase();
  if (!value) return undefined;
  if (ASSIGNEE_KEYWORDS.includes(value)) return value;
  return UUID_PATTERN.test(value) ? value : undefined;
}

function parseProject(raw: string | undefined): TaskProjectFilter | undefined {
  const value = raw?.trim().toLowerCase();
  if (!value) return undefined;
  if (value === "none") return value;
  return UUID_PATTERN.test(value) ? value : undefined;
}

function parseLabel(raw: string | undefined): TaskLabelFilter | undefined {
  const value = raw?.trim().toLowerCase();
  if (!value) return undefined;
  if (value === "none") return value;
  return UUID_PATTERN.test(value) ? value : undefined;
}

/** Whether any filter narrows the list (view, grouping and page are not filters). */
export function isFiltered(query: TaskQuery): boolean {
  return Boolean(
    query.search ||
      query.status ||
      query.priority ||
      query.assignee ||
      query.project ||
      query.label ||
      query.due,
  );
}

/** The same query with every filter removed, keeping the view and its grouping. */
export const NO_FILTERS: Partial<TaskQuery> = {
  search: undefined,
  status: undefined,
  priority: undefined,
  assignee: undefined,
  project: undefined,
  label: undefined,
  due: undefined,
};

/**
 * The URL for `query` with `changes` applied. Changing a filter or the view goes
 * back to page 1, since the old page number no longer means anything.
 */
export function taskQueryHref(
  basePath: string,
  query: TaskQuery,
  changes: Partial<TaskQuery> = {},
): string {
  const next = { ...query, ...changes };
  const resetsPage = Object.keys(changes).some((key) => key !== "page");
  const params = new URLSearchParams();
  if (next.view !== "list") params.set("view", next.view);
  if (next.view === "calendar" && next.month) params.set("month", next.month);
  if (next.group && next.view !== "calendar") params.set("group", next.group);
  if (next.search) params.set("search", next.search);
  if (next.view !== "board" && next.status) params.set("status", next.status);
  if (next.priority) params.set("priority", next.priority);
  if (next.assignee) params.set("assignee", next.assignee);
  if (next.project) params.set("project", next.project);
  if (next.label) params.set("label", next.label);
  if (next.due && next.view !== "calendar") params.set("due", next.due);
  const page = resetsPage ? 1 : next.page;
  if (next.view === "list" && page > 1) params.set("page", String(page));
  const suffix = params.toString();
  return suffix ? `${basePath}?${suffix}` : basePath;
}
