/**
 * Server-side reads for the discussion under a task: its comments, its history
 * and who watches it, fetched together.
 *
 * The newest 100 of each. Comments come oldest first, so when there are more
 * than a page the *last* page is read instead --- a long conversation shows its
 * latest turns, the way people read one. The task itself has already been
 * authorized by the page, so a failure here is shown in place rather than
 * turning the whole page into an error.
 */

import { fetchTaskActivity } from "@/features/activity/api/activity-queries";
import { fetchComments } from "@/features/comments/api/comment-queries";
import { fetchWatchers } from "@/features/notifications/api/notification-queries";
import { ApiError } from "@/lib/api/client";
import type { ActivityEvent } from "@/types/activity";
import type { TaskComment } from "@/types/comment";
import type { Watchers } from "@/types/notification";

const PAGE_SIZE = 100;

export interface TaskDiscussionData {
  readonly comments: readonly TaskComment[];
  readonly commentTotal: number;
  readonly activity: readonly ActivityEvent[];
  readonly activityTotal: number;
  /** Who follows the task; `null` if it could not be read. */
  readonly watchers: Watchers | null;
  readonly loadError: string | null;
}

export async function loadTaskDiscussion(
  taskId: string,
  cookie: string | undefined,
): Promise<TaskDiscussionData> {
  try {
    const [first, activity, watchers] = await Promise.all([
      fetchComments(taskId, { page_size: PAGE_SIZE }, cookie),
      fetchTaskActivity(taskId, { page_size: PAGE_SIZE }, cookie),
      fetchWatchers(taskId, cookie).catch(() => null),
    ]);
    const comments =
      first.pages > 1
        ? await fetchComments(taskId, { page: first.pages, page_size: PAGE_SIZE }, cookie)
        : first;
    return {
      comments: comments.items,
      commentTotal: comments.total,
      activity: activity.items,
      activityTotal: activity.total,
      watchers,
      loadError: null,
    };
  } catch (error) {
    return {
      comments: [],
      commentTotal: 0,
      activity: [],
      activityTotal: 0,
      watchers: null,
      loadError:
        error instanceof ApiError
          ? error.message
          : "The conversation could not be loaded. Please try again.",
    };
  }
}
