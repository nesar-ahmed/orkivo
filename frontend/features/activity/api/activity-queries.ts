/**
 * Typed reads against the activity log. There are no writes: the backend records
 * every event itself, in the transaction that makes the change.
 */

import { apiClient } from "@/lib/api/client";
import type { ActivityListResponse } from "@/types/activity";

export interface ActivityListParams {
  page?: number;
  page_size?: number;
}

function query(params: ActivityListParams): string {
  const search = new URLSearchParams();
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  return search.size > 0 ? `?${search.toString()}` : "";
}

/** One task's history, newest first. A task the caller cannot reach answers 404. */
export function fetchTaskActivity(
  taskId: string,
  params: ActivityListParams = {},
  cookie?: string,
): Promise<ActivityListResponse> {
  return apiClient.get<ActivityListResponse>(
    `/tasks/${taskId}/activity${query(params)}`,
    cookie ? { cookie } : {},
  );
}

/** A workspace's feed, newest first --- including tasks deleted since. */
export function fetchWorkspaceActivity(
  workspaceId: string,
  params: ActivityListParams = {},
  cookie?: string,
): Promise<ActivityListResponse> {
  return apiClient.get<ActivityListResponse>(
    `/workspaces/${workspaceId}/activity${query(params)}`,
    cookie ? { cookie } : {},
  );
}
