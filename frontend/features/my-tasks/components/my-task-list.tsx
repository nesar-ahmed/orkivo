"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import { LabelChips } from "@/features/labels/components/label-chip";
import { StatusIcon } from "@/features/tasks/components/task-icons";
import {
  BlockedChip,
  DueChip,
  PriorityChip,
  ProjectChip,
} from "@/features/tasks/components/task-meta";
import { StatusPicker } from "@/features/tasks/components/task-pickers";
import { TaskRowMenu } from "@/features/tasks/components/task-row-menu";
import {
  DUE_BUCKET_LABELS,
  DUE_BUCKET_ORDER,
  dueBucket,
  type DueBucket,
} from "@/features/tasks/task-dates";
import { STATUS_LABELS, taskCan } from "@/features/tasks/task-utils";
import { useOptimisticTasks, useTaskActions } from "@/features/tasks/use-task-actions";
import { useToday } from "@/features/tasks/use-today";
import { WorkspaceMark } from "@/features/workspaces/components/workspace-switcher";
import { taskPath } from "@/features/workspaces/workspace-utils";
import { cn } from "@/lib/utils/cn";
import type { Task, TaskStatus } from "@/types/task";
import type { Workspace } from "@/types/workspace";

const listStyles =
  "divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-xs";

/**
 * A person's own tasks, from every workspace they are in, one compact row each.
 *
 * Sorted by due date (`grouped`), the page is split into "overdue", "today",
 * "next 7 days", "later" and "no due date", on the viewer's own clock; a short
 * summary above says how much needs attention. Each row says which workspace the
 * task lives in and links to it there. What can be done to a row follows that
 * task's own `capabilities` --- a task in a suspended company, or one the caller
 * only reads, is read-only here exactly as on its board. Status changes and
 * deletes are optimistic with Undo.
 */
export function MyTaskList({
  tasks: serverTasks,
  workspaces,
  grouped,
  empty,
}: {
  tasks: readonly Task[];
  workspaces: readonly Workspace[];
  grouped: boolean;
  empty: ReactNode;
}) {
  const { tasks, put, drop } = useOptimisticTasks(serverTasks);
  const actions = useTaskActions({ put, drop });
  const today = useToday();
  const byId = new Map(workspaces.map((workspace) => [workspace.id, workspace]));

  if (tasks.length === 0) return <>{empty}</>;

  const bucketOf = (task: Task) => dueBucket(task.due_date, today, task.status === "done");
  const row = (task: Task) => (
    <MyTaskRow
      key={task.id}
      task={task}
      workspace={byId.get(task.workspace_id) ?? null}
      onStatus={(status) => void actions.changeStatus(task, status)}
      onDelete={() => actions.remove(task)}
    />
  );

  const counts = new Map<DueBucket, number>();
  for (const task of tasks) {
    if (task.status !== "done") counts.set(bucketOf(task), (counts.get(bucketOf(task)) ?? 0) + 1);
  }
  const summary = [
    counts.get("overdue") ? { text: `${counts.get("overdue")} overdue`, urgent: true } : null,
    counts.get("today") ? { text: `${counts.get("today")} due today`, urgent: false } : null,
    counts.get("week") ? { text: `${counts.get("week")} in the next 7 days`, urgent: false } : null,
  ].filter((item) => item !== null);

  return (
    <div className="flex flex-col gap-4">
      {summary.length > 0 ? (
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          {summary.map((item, index) => (
            <span key={item.text} className="inline-flex items-center gap-3">
              {index > 0 ? <span aria-hidden="true">·</span> : null}
              <span className={cn(item.urgent && "font-medium text-danger")}>{item.text}</span>
            </span>
          ))}
          <span className="sr-only"> on this page.</span>
        </p>
      ) : null}

      {grouped ? (
        DUE_BUCKET_ORDER.map((bucket) => {
          const group = tasks.filter((task) => bucketOf(task) === bucket);
          if (group.length === 0) return null;
          const headingId = `my-tasks-${bucket}`;
          return (
            <section key={bucket} aria-labelledby={headingId} className="flex flex-col gap-2">
              <h3
                id={headingId}
                className={cn(
                  "flex items-center gap-2 px-1 text-sm font-semibold",
                  bucket === "overdue" ? "text-danger" : "text-foreground",
                )}
              >
                {DUE_BUCKET_LABELS[bucket]}
                <span className="rounded-full bg-card px-1.5 text-xs font-medium text-muted-foreground ring-1 ring-border">
                  {group.length}
                  <span className="sr-only"> on this page</span>
                </span>
              </h3>
              <ul aria-labelledby={headingId} className={listStyles}>
                {group.map(row)}
              </ul>
            </section>
          );
        })
      ) : (
        <ul aria-label="My tasks" className={listStyles}>
          {tasks.map(row)}
        </ul>
      )}
    </div>
  );
}

function MyTaskRow({
  task,
  workspace,
  onStatus,
  onDelete,
}: {
  task: Task;
  /** `null` only if the task's workspace is not in the loaded list of memberships. */
  workspace: Workspace | null;
  onStatus: (status: TaskStatus) => void;
  onDelete: () => void;
}) {
  const canEdit = taskCan(task, "edit");
  const href = workspace ? taskPath(workspace, task.id) : "/app/workspaces";
  const where = workspace
    ? workspace.kind === "personal"
      ? "Private"
      : workspace.name
    : "Another workspace";

  return (
    <li className="group flex items-center gap-2 px-2 py-2 transition-colors hover:bg-muted/50 sm:gap-3 sm:px-3">
      {canEdit ? (
        <StatusPicker value={task.status} taskTitle={task.title} onChange={onStatus} />
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
        <p className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
          <WorkspaceMark workspace={workspace} className="size-4 rounded text-[0.6rem]" />
          <span className="sr-only">In </span>
          <span className="truncate">{where}</span>
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <BlockedChip task={task} />
        {task.labels.length > 0 ? (
          <span className="hidden md:inline-flex">
            <LabelChips labels={task.labels} max={2} className="flex-nowrap" />
          </span>
        ) : null}
        <span className="hidden sm:inline-flex">
          <ProjectChip task={task} />
        </span>
        <PriorityChip task={task} compact />
        <DueChip task={task} />
        <TaskRowMenu
          task={task}
          href={href}
          onMove={canEdit ? onStatus : undefined}
          onDelete={taskCan(task, "delete") ? onDelete : undefined}
        />
      </div>
    </li>
  );
}
