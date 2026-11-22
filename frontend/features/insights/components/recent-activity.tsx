import { ActivityItem } from "@/features/activity/components/activity-item";
import { taskPath } from "@/features/workspaces/workspace-utils";
import type { ActivityListResponse } from "@/types/activity";
import type { Workspace } from "@/types/workspace";

/**
 * The last few things that happened, for context next to the numbers; the
 * activity page holds the rest. A task deleted since keeps its name, unlinked,
 * as it does on the full feed.
 */
export function RecentActivity({
  workspace,
  activity,
}: {
  workspace: Pick<Workspace, "kind" | "slug">;
  activity: ActivityListResponse;
}) {
  if (activity.items.length === 0) {
    return <p className="text-sm text-muted-foreground">Nothing has happened here yet.</p>;
  }
  const deleted = new Set(
    activity.items.filter((event) => event.verb === "task.deleted").map((event) => event.task_id),
  );
  return (
    <ol className="flex flex-col gap-3">
      {activity.items.map((event) => (
        <li key={event.id}>
          <ActivityItem
            event={event}
            inTask={false}
            taskHref={
              event.task_id && !deleted.has(event.task_id)
                ? taskPath(workspace, event.task_id)
                : undefined
            }
          />
        </li>
      ))}
    </ol>
  );
}
