/** Typed reads against the notifications API: the inbox, its count, and watchers. */

import { apiClient } from "@/lib/api/client";
import type { NotificationListResponse, UnreadCount, Watchers } from "@/types/notification";

export interface NotificationListParams {
  unread?: boolean;
  page?: number;
  page_size?: number;
}

export function fetchNotifications(
  params: NotificationListParams = {},
  cookie?: string,
): Promise<NotificationListResponse> {
  const query = new URLSearchParams();
  if (params.unread) query.set("unread", "true");
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient.get<NotificationListResponse>(
    `/notifications${suffix}`,
    cookie ? { cookie } : {},
  );
}

/** Just the number, for the badge. Cheap enough to poll. */
export function fetchUnreadCount(cookie?: string): Promise<UnreadCount> {
  return apiClient.get<UnreadCount>("/notifications/unread-count", cookie ? { cookie } : {});
}

/** Who follows a task, and whether the caller does. */
export function fetchWatchers(taskId: string, cookie?: string): Promise<Watchers> {
  return apiClient.get<Watchers>(`/tasks/${taskId}/watchers`, cookie ? { cookie } : {});
}
