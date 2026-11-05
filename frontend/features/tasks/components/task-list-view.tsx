"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import { StatusIcon } from "@/features/tasks/components/task-icons";
import { CreatorAvatar, DueChip, PriorityChip } from "@/features/tasks/components/task-meta";
import { StatusPicker } from "@/features/tasks/components/task-pickers";
import { TaskRowMenu } from "@/features/tasks/components/task-row-menu";
import { STATUS_LABELS } from "@/features/tasks/task-utils";
import { useOptimisticTasks, useTaskActions } from "@/features/tasks/use-task-actions";
import { cn } from "@/lib/utils/cn";
import type { Task } from "@/types/task";

/**
 * The list view: one compact row per task, about three times as many per screen
 * as the old cards. Status changes and deletes are optimistic with Undo.
 *
 * `canEdit` comes from the workspace's capabilities; in view mode the same rows
 * render without any control, rather than with controls that would fail.
 */
export function TaskListView({
  tasks: serverTasks,
  canEdit,
  basePath,
  empty,
}: {
  tasks: readonly Task[];
  canEdit: boolean;
  basePath: string;
  empty: ReactNode;
}) {
  const { tasks, put, drop } = useOptimisticTasks(serverTasks);
  const actions = useTaskActions({ put, drop });

  if (tasks.length === 0) return <>{empty}</>;

  return (
    <ul
      aria-label="Tasks"
      className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-xs"
    >
      {tasks.map((task) => {
        const href = `${basePath}/${task.id}`;
        return (
          <li
            key={task.id}
            className="group flex items-center gap-2 px-2 py-2 transition-colors hover:bg-muted/50 sm:gap-3 sm:px-3"
          >
            {canEdit ? (
              <StatusPicker
                value={task.status}
                taskTitle={task.title}
                onChange={(status) => void actions.changeStatus(task, status)}
              />
            ) : (
              <span className="inline-flex size-7 items-center justify-center">
                <StatusIcon status={task.status} />
                <span className="sr-only">{STATUS_LABELS[task.status]}</span>
              </span>
            )}

            <div className="min-w-0 flex-1">
              <Link
                href={href}
                className={cn(
                  "block truncate rounded-sm text-sm font-medium hover:text-primary",
                  task.status === "done" ? "text-muted-foreground line-through" : "text-foreground",
                )}
              >
                {task.title}
              </Link>
              {task.description ? (
                <p className="truncate text-xs text-muted-foreground">{task.description}</p>
              ) : null}
            </div>

            <div className="flex shrink-0 items-center gap-2 sm:gap-3">
              <PriorityChip task={task} compact />
              <DueChip task={task} />
              <CreatorAvatar task={task} />
              <TaskRowMenu
                task={task}
                href={href}
                onDelete={canEdit ? () => actions.remove(task) : undefined}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
