/**
 * Typed contracts for workspace automation rules, mirroring
 * backend/app/modules/automations/schemas.py.
 *
 * A company switches catalogue rules on and off; the backend runs them inside the
 * save that triggers them. The client only reads and switches.
 */

/** What makes a rule run. */
export type AutomationTrigger = "task_completed";

/** Who a notifying rule tells. */
export type AutomationRecipient = "task_creator" | "task_watchers" | "workspace_owners";

/** The catalogue, in the order the settings page offers it. */
export type AutomationRuleKey =
  | "notify_creator_on_done"
  | "notify_watchers_on_done"
  | "notify_owners_on_done";

export interface AutomationRule {
  rule: AutomationRuleKey;
  trigger: AutomationTrigger;
  recipient: AutomationRecipient;
  enabled: boolean;
  /** `null` until someone first switches the rule; a rule nobody switched is off. */
  updated_by: { id: string; display_name: string } | null;
  updated_at: string | null;
}

/** Every rule in the catalogue. Not paginated: it is short. */
export interface AutomationRuleListResponse {
  items: AutomationRule[];
}
