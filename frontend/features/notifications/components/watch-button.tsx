"use client";

import { useState, useTransition } from "react";
import { Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { unwatchTask, watchTask } from "@/features/notifications/api/notification-mutations";
import { fetchWatchers } from "@/features/notifications/api/notification-queries";
import { ApiError } from "@/lib/api/client";
import type { Watchers } from "@/types/notification";

/**
 * Follow a task, or stop. Watchers hear about every comment on it.
 *
 * Creating, being assigned, commenting and being mentioned already make a person
 * watch, so this is mostly how someone *stops*. The count and names show who
 * will hear about a comment. It is the person's own setting, so it stays
 * available in view mode.
 */
export function WatchButton({ taskId, initial }: { taskId: string; initial: Watchers }) {
  const [watchers, setWatchers] = useState(initial);
  const [isPending, startTransition] = useTransition();

  function toggle() {
    const next = !watchers.watching;
    setWatchers((current) => ({ ...current, watching: next }));
    startTransition(async () => {
      try {
        if (next) {
          setWatchers(await watchTask(taskId));
        } else {
          await unwatchTask(taskId);
          setWatchers(await fetchWatchers(taskId));
        }
      } catch (error) {
        setWatchers((current) => ({ ...current, watching: !next }));
        toast.error("Watching could not be changed.", {
          description: error instanceof ApiError ? error.message : undefined,
        });
      }
    });
  }

  const names = watchers.items.map((person) => person.display_name);
  const who =
    names.length === 0 ? "Nobody is watching this task." : `Watching: ${names.join(", ")}`;

  return (
    <Tooltip content={who}>
      <Button
        variant={watchers.watching ? "secondary" : "ghost"}
        size="sm"
        aria-pressed={watchers.watching}
        onClick={toggle}
        disabled={isPending}
      >
        {watchers.watching ? <Eye aria-hidden="true" /> : <EyeOff aria-hidden="true" />}
        {watchers.watching ? "Watching" : "Watch"}
        <span className="rounded-full bg-muted px-1.5 text-xs text-muted-foreground">
          {watchers.items.length}
        </span>
      </Button>
    </Tooltip>
  );
}
