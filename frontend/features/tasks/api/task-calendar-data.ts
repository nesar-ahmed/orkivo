/**
 * Server-side reads for a calendar: the tasks due in the weeks a month's grid
 * shows, and the first few with no due date at all.
 *
 * Shared by a workspace's calendar and a person's own one; only the `fetchPage`
 * read differs. The grid is read in pages of the API's maximum, soonest first,
 * up to `MAX_CALENDAR_TASKS` --- a month busier than that says so rather than
 * quietly dropping days. Unscheduled tasks are a tray beside the grid: the place
 * to drag work *onto* the calendar from.
 */

import { monthGrid, type MonthKey } from "@/features/tasks/task-dates";
import { ApiError } from "@/lib/api/client";
import type { Task, TaskListResponse } from "@/types/task";

/** The API's page-size ceiling. */
const CALENDAR_PAGE_SIZE = 100;
/** The most a month's grid loads: five pages. */
export const MAX_CALENDAR_TASKS = 500;
/** How many unscheduled tasks the tray offers; the list shows them all. */
export const UNSCHEDULED_TASKS = 30;

/** One read of the underlying list, with the calendar's own parameters. */
export type CalendarPageReader = (params: {
  due_from?: string;
  due_to?: string;
  has_due_date?: boolean;
  order: "due" | "newest";
  page: number;
  page_size: number;
}) => Promise<TaskListResponse>;

export interface CalendarData {
  readonly month: MonthKey;
  /** The first and last day the grid shows (whole weeks around the month). */
  readonly first: string;
  readonly last: string;
  readonly tasks: readonly Task[];
  /** How many tasks are due in the grid's window, including any not loaded. */
  readonly total: number;
  readonly unscheduled: readonly Task[];
  readonly unscheduledTotal: number;
  readonly loadError: string | null;
}

/** The month a calendar shows when the URL names none: the current one, on the server's clock. */
export function currentMonth(): MonthKey {
  return new Date().toISOString().slice(0, 7);
}

export async function loadCalendar(
  month: MonthKey,
  fetchPage: CalendarPageReader,
): Promise<CalendarData> {
  const { first, last } = monthGrid(month);
  try {
    const [scheduled, unscheduled] = await Promise.all([
      readWindow(first, last, fetchPage),
      fetchPage({ has_due_date: false, order: "newest", page: 1, page_size: UNSCHEDULED_TASKS }),
    ]);
    return {
      month,
      first,
      last,
      tasks: scheduled.tasks,
      total: scheduled.total,
      unscheduled: unscheduled.items,
      unscheduledTotal: unscheduled.total,
      loadError: null,
    };
  } catch (error) {
    return {
      month,
      first,
      last,
      tasks: [],
      total: 0,
      unscheduled: [],
      unscheduledTotal: 0,
      loadError:
        error instanceof ApiError ? error.message : "Failed to load tasks. Please try again.",
    };
  }
}

async function readWindow(
  first: string,
  last: string,
  fetchPage: CalendarPageReader,
): Promise<{ tasks: Task[]; total: number }> {
  const window = { due_from: first, due_to: last, order: "due" as const };
  const opening = await fetchPage({ ...window, page: 1, page_size: CALENDAR_PAGE_SIZE });
  const pages = Math.min(opening.pages, MAX_CALENDAR_TASKS / CALENDAR_PAGE_SIZE);
  const rest = await Promise.all(
    Array.from({ length: Math.max(pages - 1, 0) }, (_, index) =>
      fetchPage({ ...window, page: index + 2, page_size: CALENDAR_PAGE_SIZE }),
    ),
  );
  return {
    tasks: [opening, ...rest].flatMap((page) => page.items),
    total: opening.total,
  };
}
