/**
 * Typed reads of the dashboards API.
 *
 * Both take the viewer's own day, so "overdue" means what it means on their
 * calendar; server renders pass `getViewerToday()`.
 */

import { apiClient } from "@/lib/api/client";
import type { MyStats, WorkspaceStats } from "@/types/insights";

export function fetchWorkspaceStats(
  workspaceId: string,
  today: string,
  cookie?: string,
): Promise<WorkspaceStats> {
  return apiClient.get<WorkspaceStats>(
    `/workspaces/${workspaceId}/stats?today=${encodeURIComponent(today)}`,
    cookie ? { cookie } : {},
  );
}

export function fetchMyStats(today: string, cookie?: string): Promise<MyStats> {
  return apiClient.get<MyStats>(
    `/me/stats?today=${encodeURIComponent(today)}`,
    cookie ? { cookie } : {},
  );
}
