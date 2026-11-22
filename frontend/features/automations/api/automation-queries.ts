/** Typed reads of a workspace's automation rules. Any member may read them. */

import { apiClient } from "@/lib/api/client";
import type { AutomationRuleListResponse } from "@/types/automation";

export function fetchAutomations(
  workspaceId: string,
  cookie?: string,
): Promise<AutomationRuleListResponse> {
  return apiClient.get<AutomationRuleListResponse>(
    `/workspaces/${workspaceId}/automations`,
    cookie ? { cookie } : {},
  );
}
