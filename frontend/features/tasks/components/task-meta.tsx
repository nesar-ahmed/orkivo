import { Ban, CalendarDays, FolderKanban, UserRound } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { Tooltip } from "@/components/ui/tooltip";
import { PriorityIcon } from "@/features/tasks/components/task-icons";
import { PRIORITY_LABELS, formatDueDate, isOverdue } from "@/features/tasks/task-utils";
import { cn } from "@/lib/utils/cn";
import type { Task } from "@/types/task";

/** Priority as icon + word (the word hides on narrow rows but stays announced). */
export function PriorityChip({ task, compact }: { task: Task; compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <PriorityIcon priority={task.priority} className="size-3.5" />
      <span className={compact ? "sr-only" : undefined}>
        {PRIORITY_LABELS[task.priority]}
        <span className="sr-only"> priority</span>
      </span>
    </span>
  );
}

/** The due date; red and prefixed with "Overdue" when it has passed. */
export function DueChip({ task }: { task: Task }) {
  if (!task.due_date) return null;
  const overdue = isOverdue(task);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs whitespace-nowrap",
        overdue ? "bg-danger/10 font-medium text-danger" : "text-muted-foreground",
      )}
    >
      <CalendarDays aria-hidden="true" className="size-3.5" />
      {overdue ? <span className="sr-only">Overdue, due </span> : <span className="sr-only">Due </span>}
      {formatDueDate(task.due_date)}
    </span>
  );
}

/**
 * "Blocked" while the task waits on unfinished tasks; nothing otherwise. How many
 * is on hover and for screen readers. A warning, never a lock: the task can still
 * be moved.
 */
export function BlockedChip({ task, compact }: { task: Task; compact?: boolean }) {
  const count = task.open_blocker_count;
  if (count === 0) return null;
  const label = `Blocked: waiting on ${count} open ${count === 1 ? "task" : "tasks"}`;
  return (
    <Tooltip content={label}>
      <span
        tabIndex={0}
        className="inline-flex shrink-0 items-center gap-1 rounded-md bg-warning/10 px-1.5 py-0.5 text-xs font-medium whitespace-nowrap text-warning"
      >
        <Ban aria-hidden="true" className="size-3.5" />
        <span className={compact ? "sr-only" : undefined}>Blocked</span>
        <span className="sr-only">: waiting on {count} open {count === 1 ? "task" : "tasks"}</span>
      </span>
    </Tooltip>
  );
}

/** The project a task is filed under, if any: a quiet label, never a control. */
export function ProjectChip({ task }: { task: Task }) {
  if (!task.project) return null;
  return (
    <span className="inline-flex max-w-40 min-w-0 items-center gap-1 text-xs text-muted-foreground">
      <FolderKanban aria-hidden="true" className="size-3.5 shrink-0" />
      <span className="sr-only">Project: </span>
      <span className="truncate">{task.project.name}</span>
    </span>
  );
}

/**
 * Who holds the task, as an avatar --- or a dashed empty circle when nobody does.
 * The name, and who created and last edited the task, are on hover and for
 * screen readers, so the picture is never the only place they live.
 */
export function AssigneeAvatar({ task }: { task: Task }) {
  const creator = task.created_by?.display_name ?? "a former member";
  const editor =
    task.updated_by && task.updated_by.id !== task.created_by?.id
      ? `, last edited by ${task.updated_by.display_name}`
      : "";
  const holder = task.assignee ? `Assigned to ${task.assignee.display_name}` : "Unassigned";
  const label = `${holder}. Created by ${creator}${editor}.`;
  return (
    <Tooltip content={label}>
      <span tabIndex={0} className="inline-flex rounded-full">
        {task.assignee ? (
          <Avatar
            name={task.assignee.display_name}
            seed={task.assignee.id}
            size="sm"
            label={label}
          />
        ) : (
          <UnassignedAvatar size="sm" label={label} />
        )}
      </span>
    </Tooltip>
  );
}

/** The empty seat: same footprint as an avatar, so rows and cards stay aligned. */
export function UnassignedAvatar({
  size = "sm",
  label,
}: {
  size?: "xs" | "sm";
  label?: string;
}) {
  return (
    <span
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full border border-dashed border-border-strong text-muted-foreground",
        size === "xs" ? "size-5" : "size-6",
      )}
    >
      <UserRound aria-hidden="true" className={size === "xs" ? "size-3" : "size-3.5"} />
    </span>
  );
}
