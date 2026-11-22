/**
 * How automation rules are described to people.
 *
 * Copy only: what each rule does is the backend's catalogue, and the API says
 * every rule's trigger and recipient, so a new rule only needs its words here.
 */

import type {
  AutomationRecipient,
  AutomationRuleKey,
  AutomationTrigger,
} from "@/types/automation";

/** "When …" */
export const TRIGGER_LABELS: Record<AutomationTrigger, string> = {
  task_completed: "A task is moved to Done",
};

/** "Then …" */
export const RECIPIENT_LABELS: Record<AutomationRecipient, string> = {
  task_creator: "Notify the person who created it",
  task_watchers: "Notify everyone watching it",
  workspace_owners: "Notify the workspace owners",
};

/** One line on what switching the rule on means for people. */
export const RULE_DESCRIPTIONS: Record<AutomationRuleKey, string> = {
  notify_creator_on_done:
    "Whoever asked for the work hears that it is finished, wherever they are in the company.",
  notify_watchers_on_done:
    "Everyone following a task — its creator, its assignee and anyone who commented or chose to watch — hears that it is finished.",
  notify_owners_on_done:
    "The company's owners hear about every finished task, without having to watch each one.",
};
