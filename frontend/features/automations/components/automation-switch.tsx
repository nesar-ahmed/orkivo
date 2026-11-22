"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { setAutomationEnabled } from "@/features/automations/api/automation-mutations";
import { ApiError } from "@/lib/api/client";
import type { AutomationRuleKey } from "@/types/automation";

/**
 * Switch one rule on or off. The switch moves at once and the change is saved
 * straight away --- a setting, not a form --- and it moves back, saying why, if the
 * API refuses (a role or suspension that changed since the page loaded).
 */
export function AutomationSwitch({
  workspaceId,
  rule,
  enabled,
  label,
}: {
  workspaceId: string;
  rule: AutomationRuleKey;
  enabled: boolean;
  /** The rule's name, for the switch's accessible name and the notification. */
  label: string;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [shown, setShown] = useState(enabled);
  const [synced, setSynced] = useState(enabled);

  // A refreshed server render brought the saved state: show it.
  if (enabled !== synced) {
    setSynced(enabled);
    setShown(enabled);
  }

  function handleChange(next: boolean) {
    setShown(next);
    startTransition(async () => {
      try {
        await setAutomationEnabled(workspaceId, rule, next);
        toast(next ? "Automation switched on" : "Automation switched off", { description: label });
        router.refresh();
      } catch (error) {
        setShown(!next);
        toast.error("The automation could not be switched", {
          description: error instanceof ApiError ? error.message : undefined,
        });
        router.refresh();
      }
    });
  }

  return (
    <Switch
      checked={shown}
      onCheckedChange={handleChange}
      disabled={isPending}
      aria-label={label}
    />
  );
}
