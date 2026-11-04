"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { ApiError } from "@/lib/api/client";
import { deleteTask, updateTask } from "@/features/tasks/api/task-mutations";
import {
  PRIORITY_BADGES,
  PRIORITY_LABELS,
  STATUS_BADGES,
  STATUS_LABELS,
  STATUS_ORDER,
  formatDueDate,
  isOverdue,
} from "@/features/tasks/task-utils";
import type { Task, TaskStatus } from "@/types/task";

export function TaskCard({ task }: { task: Task }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function run(action: () => Promise<void>, successMessage: string) {
    startTransition(async () => {
      try {
        await action();
        setError(null);
        router.refresh();
      } catch (err) {
        setError(
          err instanceof ApiError
            ? `${successMessage} (${err.message})`
            : `${successMessage} (unexpected error)`,
        );
      }
    });
  }

  function handleStatusChange(status: TaskStatus) {
    run(async () => {
      await updateTask(task.id, { status });
    }, `Could not move task to "${STATUS_LABELS[status]}".`);
  }

  function handleDelete() {
    if (!window.confirm(`Delete "${task.title}"? This cannot be undone.`)) return;
    run(async () => {
      await deleteTask(task.id);
    }, "Could not delete the task.");
  }

  const overdue = isOverdue(task);

  return (
    <li aria-busy={isPending} className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <h3
          className={
            task.status === "done"
              ? "text-sm font-medium text-muted-foreground line-through"
              : "text-sm font-semibold text-card-foreground"
          }
        >
          {task.title}
        </h3>
        <Badge variant={STATUS_BADGES[task.status]}>{STATUS_LABELS[task.status]}</Badge>
      </div>

      {task.description ? (
        <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">{task.description}</p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <Badge variant={PRIORITY_BADGES[task.priority]}>
          {PRIORITY_LABELS[task.priority]} priority
        </Badge>
        {task.due_date ? (
          <Badge variant={overdue ? "danger" : "neutral"}>
            {overdue ? "Overdue · " : "Due "}
            {formatDueDate(task.due_date)}
          </Badge>
        ) : null}
      </div>

      <div className="mt-4 flex items-center gap-2">
        <label className="sr-only" htmlFor={`status-${task.id}`}>
          Change status for {task.title}
        </label>
        <Select
          id={`status-${task.id}`}
          className="h-8 w-36 text-xs"
          value={task.status}
          disabled={isPending}
          onChange={(event) => handleStatusChange(event.target.value as TaskStatus)}
        >
          {STATUS_ORDER.map((status) => (
            <option key={status} value={status}>
              {STATUS_LABELS[status]}
            </option>
          ))}
        </Select>
        <Button
          variant="danger"
          size="sm"
          className="ml-auto"
          disabled={isPending}
          onClick={handleDelete}
        >
          Delete
        </Button>
      </div>

      {error ? (
        <p role="alert" className="mt-2 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </li>
  );
}
