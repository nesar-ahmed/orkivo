/**
 * Server-side reads for a person's own list, shaped for the view the URL asks for.
 *
 * The list is one page of `/me/tasks` in the chosen order; the calendar is the
 * weeks around one month, read through the same shared calendar loader a
 * workspace's calendar uses. A due filter becomes a window of dates on the
 * viewer's own day, exactly as on a board (`dueWindow`). Every read runs as the visitor, so which workspaces
 * count as theirs is the backend's decision.
 */

import {
  currentMonth,
  loadCalendar,
  type CalendarData,
} from "@/features/tasks/api/task-calendar-data";
import { fetchMyTasks, type MyTaskListParams } from "@/features/tasks/api/task-queries";
import { apiStatus, type MyTaskQuery } from "@/features/my-tasks/my-task-query";
import { dueWindow } from "@/features/tasks/task-dates";
import { ApiError } from "@/lib/api/client";
import { getViewerToday } from "@/lib/api/server-cookies";
import type { TaskListResponse } from "@/types/task";

export const MY_TASKS_PER_PAGE = 50;

export interface MyTaskViewData {
  readonly list: TaskListResponse | null;
  readonly calendar: CalendarData | null;
  readonly loadError: string | null;
}

export async function loadMyTaskView(
  query: MyTaskQuery,
  cookie: string | undefined,
): Promise<MyTaskViewData> {
  const dueRange = query.due ? dueWindow(query.due, await getViewerToday()) : null;
  const filters: MyTaskListParams = {
    search: query.search,
    // Overdue is open work only; a list already showing only open work is unchanged.
    status: dueRange?.openOnly && query.status === "all" ? "open" : apiStatus(query.status),
    priority: query.priority,
    workspace: query.workspace,
    due_from: dueRange?.due_from,
    due_to: dueRange?.due_to,
    has_due_date: dueRange?.has_due_date,
  };
  if (query.view === "calendar") {
    const calendar = await loadCalendar(query.month ?? currentMonth(), (page) =>
      fetchMyTasks({ ...filters, ...page }, cookie),
    );
    return { list: null, calendar, loadError: calendar.loadError };
  }
  try {
    const list = await fetchMyTasks(
      { ...filters, order: query.order, page: query.page, page_size: MY_TASKS_PER_PAGE },
      cookie,
    );
    return { list, calendar: null, loadError: null };
  } catch (error) {
    return {
      list: null,
      calendar: null,
      loadError:
        error instanceof ApiError ? error.message : "Failed to load your tasks. Please try again.",
    };
  }
}
