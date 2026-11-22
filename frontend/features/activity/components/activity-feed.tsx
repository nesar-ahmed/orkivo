import { History } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination } from "@/components/ui/pagination";
import { ActivityItem } from "@/features/activity/components/activity-item";
import { taskPath, workspacePath } from "@/features/workspaces/workspace-utils";
import type { ActivityListResponse } from "@/types/activity";
import type { Workspace } from "@/types/workspace";

/**
 * Everything that happened in one workspace, newest first.
 *
 * Tasks are linked while they exist. A task deleted since still appears, by the
 * name it had: the log is append-only, and this is where a deletion stays visible.
 */
export function ActivityFeed({
  workspace,
  activity,
}: {
  workspace: Workspace;
  activity: ActivityListResponse;
}) {
  // Any task deleted on this page keeps its events here, but no longer has a page.
  const deleted = new Set(
    activity.items.filter((e) => e.verb === "task.deleted").map((e) => e.task_id),
  );

  return (
    <section aria-labelledby="activity-heading" className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <h2 id="activity-heading" className="text-lg font-semibold tracking-tight">
          Activity
        </h2>
        <Badge variant="neutral">{activity.total}</Badge>
      </div>

      {activity.items.length === 0 ? (
        <EmptyState
          icon={<History />}
          title="Nothing has happened yet"
          description="Tasks created, moved, assigned, commented on or deleted here will show up in this feed."
        />
      ) : (
        <ol className="flex flex-col divide-y divide-border rounded-xl border border-border bg-card shadow-xs">
          {activity.items.map((event) => (
            <li key={event.id} className="px-4 py-3">
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
      )}

      <Pagination
        page={activity.page}
        pages={activity.pages}
        total={activity.total}
        basePath={workspacePath(workspace, "activity")}
        noun="events"
      />
    </section>
  );
}
