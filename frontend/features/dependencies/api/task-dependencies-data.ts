/**
 * Server-side read of a task's dependencies, for its page.
 *
 * The task itself has already been authorized by the page, so a failure here is
 * shown in place --- like the discussion's --- rather than turning the whole page
 * into an error.
 */

import { fetchDependencies } from "@/features/dependencies/api/dependency-queries";
import { ApiError } from "@/lib/api/client";
import type { TaskDependencies } from "@/types/dependency";

export interface TaskDependenciesData {
  readonly dependencies: TaskDependencies | null;
  readonly loadError: string | null;
}

export async function loadTaskDependencies(
  taskId: string,
  cookie: string | undefined,
): Promise<TaskDependenciesData> {
  try {
    return { dependencies: await fetchDependencies(taskId, cookie), loadError: null };
  } catch (error) {
    return {
      dependencies: null,
      loadError:
        error instanceof ApiError ? error.message : "Dependencies could not be loaded.",
    };
  }
}
