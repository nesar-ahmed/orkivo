/**
 * A board's state, as it lives in the URL: `?view=board&priority=high&search=…`.
 *
 * The URL is the single source of truth, so a filtered view can be shared,
 * bookmarked and restored with the back button. Anything unrecognised in the
 * query string is ignored rather than sent to the API.
 */

import { parsePageParam } from "@/lib/utils/page-param";
import type { TaskPriority, TaskStatus } from "@/types/task";

export type TaskView = "list" | "board";

export interface TaskQuery {
  readonly view: TaskView;
  readonly search?: string;
  /** List view only: the board already splits by status. */
  readonly status?: TaskStatus;
  readonly priority?: TaskPriority;
  readonly page: number;
}

const STATUSES: readonly TaskStatus[] = ["todo", "in_progress", "done"];
const PRIORITIES: readonly TaskPriority[] = ["low", "medium", "high"];
const MAX_SEARCH = 200;

type RawParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export function parseTaskQuery(params: RawParams): TaskQuery {
  const view: TaskView = first(params.view) === "board" ? "board" : "list";
  const search = first(params.search)?.trim().slice(0, MAX_SEARCH) || undefined;
  const status = STATUSES.find((value) => value === first(params.status));
  const priority = PRIORITIES.find((value) => value === first(params.priority));
  return {
    view,
    search,
    status: view === "list" ? status : undefined,
    priority,
    page: view === "list" ? parsePageParam(first(params.page)) : 1,
  };
}

/** Whether any filter narrows the list (view and page are not filters). */
export function isFiltered(query: TaskQuery): boolean {
  return Boolean(query.search || query.status || query.priority);
}

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
  if (next.view === "board") params.set("view", "board");
  if (next.search) params.set("search", next.search);
  if (next.view === "list" && next.status) params.set("status", next.status);
  if (next.priority) params.set("priority", next.priority);
  const page = resetsPage ? 1 : next.page;
  if (next.view === "list" && page > 1) params.set("page", String(page));
  const suffix = params.toString();
  return suffix ? `${basePath}?${suffix}` : basePath;
}
