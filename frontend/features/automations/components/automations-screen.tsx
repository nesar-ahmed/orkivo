import { ArrowRight, BellRing, CircleCheck, Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { AutomationSwitch } from "@/features/automations/components/automation-switch";
import {
  RECIPIENT_LABELS,
  RULE_DESCRIPTIONS,
  TRIGGER_LABELS,
} from "@/features/automations/automation-utils";
import { formatTimestamp } from "@/features/tasks/task-utils";
import { hasCapability, readOnlyReason } from "@/features/workspaces/workspace-utils";
import type { AutomationRuleListResponse } from "@/types/automation";
import type { Workspace } from "@/types/workspace";

/**
 * A company's automation rules: what happens on its own when work changes.
 *
 * Each rule reads as a recipe --- *when* something happens, *then* something
 * follows --- the way monday.com's and Asana's automation builders put it, with
 * one switch and who last flipped it. Every member sees which rules are on, since
 * they decide who hears about their work; switching takes `manage_automations`
 * (owners, admins and managers). Without it, the same cards render with their
 * state instead of a switch, rather than with a switch that would fail.
 */
export function AutomationsScreen({
  workspace,
  rules,
}: {
  workspace: Workspace;
  rules: AutomationRuleListResponse;
}) {
  const canSwitch = hasCapability(workspace, "manage_automations");
  const switchedOn = rules.items.filter((rule) => rule.enabled).length;

  return (
    <section aria-labelledby="automations-heading" className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h2 id="automations-heading" className="text-lg font-semibold tracking-tight">
            Automations
          </h2>
          <Badge variant={switchedOn > 0 ? "success" : "neutral"}>{switchedOn} on</Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          Rules that run on their own when work changes, for every task in this company. Nobody is
          ever notified about something they did themselves.
        </p>
      </div>

      {canSwitch ? null : (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Lock aria-hidden="true" className="size-4" />
          {readOnlyReason(workspace) === "suspended"
            ? "View mode: automations can be seen, but not switched while this company is suspended."
            : "Your role lets you see which automations are on, but not switch them."}
        </p>
      )}

      <ul className="flex flex-col gap-3">
        {rules.items.map((rule) => {
          const title = RECIPIENT_LABELS[rule.recipient];
          return (
            <li
              key={rule.rule}
              className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-xs sm:flex-row sm:items-start sm:gap-5"
            >
              <div className="flex min-w-0 flex-1 flex-col gap-2">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    When
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-md bg-muted px-2 py-1 font-medium">
                    <CircleCheck aria-hidden="true" className="size-4 text-status-done" />
                    {TRIGGER_LABELS[rule.trigger]}
                  </span>
                  <ArrowRight aria-hidden="true" className="size-4 text-muted-foreground" />
                  <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    Then
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-md bg-primary/10 px-2 py-1 font-medium text-primary">
                    <BellRing aria-hidden="true" className="size-4" />
                    {title}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground">{RULE_DESCRIPTIONS[rule.rule]}</p>
                <p className="text-xs text-muted-foreground">
                  {rule.updated_by && rule.updated_at
                    ? `Switched ${rule.enabled ? "on" : "off"} by ${rule.updated_by.display_name} · ${formatTimestamp(rule.updated_at)}`
                    : "Off — nobody has switched it on yet."}
                </p>
              </div>
              <div className="flex items-center gap-2 sm:pt-1">
                {canSwitch ? (
                  <AutomationSwitch
                    workspaceId={workspace.id}
                    rule={rule.rule}
                    enabled={rule.enabled}
                    label={title}
                  />
                ) : (
                  <Badge variant={rule.enabled ? "success" : "neutral"}>
                    {rule.enabled ? "On" : "Off"}
                  </Badge>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
