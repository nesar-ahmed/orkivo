/**
 * Server-side reads for a board, shaped for the view the URL asks for.
 *
 * The list view is one page of the filtered list --- sorted by project when it is
 * grouped, so each project's tasks arrive together and pages split between
 * groups rather than scattering them. The board view is one request per status
 * column (the newest 100 each, with the column's real total), so a busy column
 * never crowds the others out; grouping the board into project lanes happens on
 * those same tasks. The calendar view is the weeks around one month, read by due
 * date (see `task-calendar-data.ts`). All use only filters the API supports.
 *
 * A due filter (`?due=overdue`) becomes a window of dates on the viewer's own day
 * (`getViewerToday`). "Overdue" only ever means open work: the list is narrowed to
 * it unless the URL picks a status, and a board's Done column is left empty.
 */

import {
  currentMonth,
  loadCalendar,
  type CalendarData,
} from "@/features/tasks/api/task-calendar-data";
import { fetchTasks, type TaskListParams } from "@/features/tasks/api/task-queries";
import { dueWindow } from "@/features/tasks/task-dates";
import type { BoardColumnData } from "@/features/tasks/components/task-board-view";
import { taskQueryHref, type TaskQuery } from "@/features/tasks/task-query";
import { STATUS_ORDER } from "@/features/tasks/task-utils";
import { ApiError } from "@/lib/api/client";
import { getViewerToday } from "@/lib/api/server-cookies";
import type { TaskListResponse } from "@/types/task";

export const TASKS_PER_PAGE = 50;
export const TASKS_PER_COLUMN = 100;

/** A column nothing can fall into under the current filter. */
const EMPTY_PAGE: TaskListResponse = { items: [], total: 0, page: 1, page_size: 0, pages: 0 };

export interface TaskViewData {
  readonly list: TaskListResponse | null;
  readonly columns: readonly BoardColumnData[] | null;
  readonly calendar: CalendarData | null;
  /** Grouped list only: the page's first project group began on the previous page. */
  readonly continuesGroup: boolean;
  readonly loadError: string | null;
}

export async function loadTaskView(
  workspaceId: string,
  query: TaskQuery,
  basePath: string,
  cookie: string | undefined,
): Promise<TaskViewData> {
  const dueRange = query.due ? dueWindow(query.due, await getViewerToday()) : null;
  const filters = {
    search: query.search,
    priority: query.priority,
    assignee: query.assignee,
    project: query.project,
    label: query.label,
    due_from: dueRange?.due_from,
    due_to: dueRange?.due_to,
    has_due_date: dueRange?.has_due_date,
  };
  const openOnly = dueRange?.openOnly ?? false;
  if (query.view === "calendar") {
    const calendar = await loadCalendar(query.month ?? currentMonth(), (page) =>
      fetchTasks(workspaceId, { ...filters, status: query.status, ...page }, cookie),
    );
    return {
      list: null,
      columns: null,
      calendar,
      continuesGroup: false,
      loadError: calendar.loadError,
    };
  }
  try {
    if (query.view === "board") {
      const pages = await Promise.all(
        STATUS_ORDER.map((status) =>
          openOnly && status === "done"
            ? Promise.resolve<TaskListResponse>(EMPTY_PAGE)
            : fetchTasks(workspaceId, { ...filters, status, page_size: TASKS_PER_COLUMN }, cookie),
        ),
      );
      const columns = STATUS_ORDER.map((status, index) => ({
        status,
        tasks: pages[index]!.items,
        total: pages[index]!.total,
        listHref: taskQueryHref(basePath, query, { view: "list", status }),
      }));
      return { list: null, columns, calendar: null, continuesGroup: false, loadError: null };
    }
    const grouped = query.group === "project";
    const listFilters: TaskListParams = {
      ...filters,
      status: query.status ?? (openOnly ? "open" : undefined),
      order: grouped ? "project" : undefined,
    };
    const [list, previous] = await Promise.all([
      fetchTasks(
        workspaceId,
        { ...listFilters, page: query.page, page_size: TASKS_PER_PAGE },
        cookie,
      ),
      // With one task per page, page N *is* task N: this is the last task of the
      // previous page, which says whether this page's first group started there.
      grouped && query.page > 1
        ? fetchTasks(
            workspaceId,
            { ...listFilters, page: (query.page - 1) * TASKS_PER_PAGE, page_size: 1 },
            cookie,
          ).then((page) => page.items[0] ?? null)
        : Promise.resolve(null),
    ]);
    const first = list.items[0];
    const continuesGroup =
      previous !== null &&
      first !== undefined &&
      (previous.project?.id ?? null) === (first.project?.id ?? null);
    return { list, columns: null, calendar: null, continuesGroup, loadError: null };
  } catch (error) {
    return {
      list: null,
      columns: null,
      calendar: null,
      continuesGroup: false,
      loadError:
        error instanceof ApiError ? error.message : "Failed to load tasks. Please try again.",
    };
  }
}
