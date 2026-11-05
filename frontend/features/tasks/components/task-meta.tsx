import { CalendarDays } from "lucide-react";
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

/** Who created the task, as an avatar with the name on hover and for screen readers. */
export function CreatorAvatar({ task }: { task: Task }) {
  const name = task.created_by?.display_name ?? "A former member";
  const edited = task.updated_by && task.updated_by.id !== task.created_by?.id;
  const label = edited
    ? `Created by ${name}, last edited by ${task.updated_by!.display_name}`
    : `Created by ${name}`;
  return (
    <Tooltip content={label}>
      <span tabIndex={0} className="inline-flex rounded-full">
        <Avatar name={name} seed={task.created_by?.id} size="sm" label={label} />
      </span>
    </Tooltip>
  );
}
