import type { ReactNode } from "react";
import Link from "next/link";
import { StatusIcon } from "@/features/tasks/components/task-icons";
import { AssigneeAvatar, DueChip, PriorityChip } from "@/features/tasks/components/task-meta";
import { STATUS_LABELS } from "@/features/tasks/task-utils";
import { CardLoadError } from "@/features/insights/components/dashboard-card";
import type { Task } from "@/types/task";

/**
 * A short list of tasks that need someone: overdue, or due soon. Soonest first,
 * as the API sorted them, and capped --- a dashboard points at work, the list
 * behind "See all" holds it.
 *
 * `where` adds something to each row --- the workspace, on a person's own
 * dashboard, where the tasks come from everywhere. There every task is the
 * viewer's own, so `showAssignee` is off, as on their own list.
 */
export function AttentionList({
  title,
  tasks,
  total,
  empty,
  hrefFor,
  seeAll,
  where,
  showAssignee = true,
}: {
  title: string;
  tasks: readonly Task[] | null;
  total: number;
  empty: string;
  hrefFor: (task: Task) => string;
  seeAll: string;
  where?: (task: Task) => ReactNode;
  showAssignee?: boolean;
}) {
  const headingId = `attention-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="flex items-center gap-2">
        <h4 id={headingId} className="text-xs font-medium text-muted-foreground">
          {title}
        </h4>
        <span className="rounded-full bg-muted px-1.5 text-xs font-medium text-muted-foreground tabular-nums">
          {total}
        </span>
        {total > (tasks?.length ?? 0) ? (
          <Link
            href={seeAll}
            className="ml-auto text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            See all {total}
          </Link>
        ) : null}
      </div>
      {tasks === null ? (
        <CardLoadError what={title} />
      ) : tasks.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-3 py-2.5 text-xs text-muted-foreground">
          {empty}
        </p>
      ) : (
        <ul
          aria-labelledby={headingId}
          className="divide-y divide-border overflow-hidden rounded-lg border border-border"
        >
          {tasks.map((task) => (
            <li key={task.id} className="flex items-center gap-2 px-2.5 py-2">
              <StatusIcon status={task.status} />
              <span className="sr-only">{STATUS_LABELS[task.status]}: </span>
              <span className="min-w-0 flex-1">
                <Link
                  href={hrefFor(task)}
                  className="block truncate text-sm font-medium text-card-foreground hover:text-primary"
                >
                  {task.title}
                </Link>
                {where ? (
                  <span className="block truncate text-xs text-muted-foreground">{where(task)}</span>
                ) : null}
              </span>
              <PriorityChip task={task} compact />
              <DueChip task={task} />
              {showAssignee ? <AssigneeAvatar task={task} /> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
