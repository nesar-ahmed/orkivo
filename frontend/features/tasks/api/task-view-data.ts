/**
 * Server-side reads for a board, shaped for the view the URL asks for.
 *
 * The list view is one page of the filtered list. The board view is one request
 * per status column (the newest 100 each, with the column's real total), so a
 * busy column never crowds the others out. Both use only filters the API
 * already supports.
 */

import { fetchTasks } from "@/features/tasks/api/task-queries";
import type { BoardColumnData } from "@/features/tasks/components/task-board-view";
import { taskQueryHref, type TaskQuery } from "@/features/tasks/task-query";
import { STATUS_ORDER } from "@/features/tasks/task-utils";
import { ApiError } from "@/lib/api/client";
import type { TaskListResponse } from "@/types/task";

export const TASKS_PER_PAGE = 50;
export const TASKS_PER_COLUMN = 100;

export interface TaskViewData {
  readonly list: TaskListResponse | null;
  readonly columns: readonly BoardColumnData[] | null;
  readonly loadError: string | null;
}

export async function loadTaskView(
  workspaceId: string,
  query: TaskQuery,
  basePath: string,
  cookie: string | undefined,
): Promise<TaskViewData> {
  const filters = { search: query.search, priority: query.priority };
  try {
    if (query.view === "board") {
      const pages = await Promise.all(
        STATUS_ORDER.map((status) =>
          fetchTasks(workspaceId, { ...filters, status, page_size: TASKS_PER_COLUMN }, cookie),
        ),
      );
      const columns = STATUS_ORDER.map((status, index) => ({
        status,
        tasks: pages[index]!.items,
        total: pages[index]!.total,
        listHref: taskQueryHref(basePath, query, { view: "list", status }),
      }));
      return { list: null, columns, loadError: null };
    }
    const list = await fetchTasks(
      workspaceId,
      { ...filters, status: query.status, page: query.page, page_size: TASKS_PER_PAGE },
      cookie,
    );
    return { list, columns: null, loadError: null };
  } catch (error) {
    return {
      list: null,
      columns: null,
      loadError:
        error instanceof ApiError ? error.message : "Failed to load tasks. Please try again.",
    };
  }
}
