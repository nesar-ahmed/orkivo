import Link from "next/link";
import { Zap } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { describeActivity, isAutomated } from "@/features/activity/activity-utils";
import { formatTimestamp } from "@/features/tasks/task-utils";
import type { ActivityEvent } from "@/types/activity";

/**
 * One event as a line: who, what, when. On a workspace's feed the task is named
 * and linked (`taskHref`); on the task's own timeline it is simply "this task".
 * What an automation did reads with "Automation" as its subject, so it is never
 * mistaken for something the person whose change set it off did by hand.
 */
export function ActivityItem({
  event,
  inTask,
  taskHref,
}: {
  event: ActivityEvent;
  inTask: boolean;
  /** Where the task lives, when it still does. */
  taskHref?: string;
}) {
  const automated = isAutomated(event);
  const who = automated ? "Automation" : (event.actor?.display_name ?? "A former member");
  return (
    <div className="flex items-start gap-2.5 text-sm">
      {automated ? (
        <span
          aria-hidden="true"
          className="mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"
        >
          <Zap className="size-3" />
        </span>
      ) : (
        <Avatar name={who} seed={event.actor?.id} size="xs" className="mt-0.5" />
      )}
      <p className="min-w-0 flex-1 text-muted-foreground">
        <span className="font-medium text-foreground">{who}</span>{" "}
        {describeActivity(event, { inTask })}
        {taskHref ? (
          <>
            {" · "}
            <Link href={taskHref} className="font-medium text-foreground hover:text-primary">
              Open task
            </Link>
          </>
        ) : null}
        <span className="block text-xs">
          <time dateTime={event.created_at}>{formatTimestamp(event.created_at)}</time>
        </span>
      </p>
    </div>
  );
}
