/**
 * Switching a workspace's automation rules. Owners, admins and managers of an
 * active company; anyone else is refused by the API with 403.
 */

import { apiClient } from "@/lib/api/client";
import type { AutomationRule, AutomationRuleKey } from "@/types/automation";

export function setAutomationEnabled(
  workspaceId: string,
  rule: AutomationRuleKey,
  enabled: boolean,
): Promise<AutomationRule> {
  return apiClient.patch<AutomationRule>(`/workspaces/${workspaceId}/automations/${rule}`, {
    enabled,
  });
}
