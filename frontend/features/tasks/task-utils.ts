/** Presentation metadata and small helpers for the tasks feature. */

import type { BadgeVariant } from "@/components/ui/badge";
import type { Task, TaskPriority, TaskStatus } from "@/types/task";

export const STATUS_ORDER: TaskStatus[] = ["todo", "in_progress", "done"];

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
};

export const STATUS_BADGES: Record<TaskStatus, BadgeVariant> = {
  todo: "neutral",
  in_progress: "warning",
  done: "success",
};

export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

export const PRIORITY_BADGES: Record<TaskPriority, BadgeVariant> = {
  low: "neutral",
  medium: "info",
  high: "danger",
};

/** Format an ISO date (YYYY-MM-DD) for display without timezone surprises. */
export function formatDueDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  if (!year || !month || !day) return isoDate;
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.toLocaleDateString("en-US", {
    timeZone: "UTC",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** A task is overdue when its due date passed and it is not done. */
export function isOverdue(task: Task): boolean {
  if (!task.due_date || task.status === "done") return false;
  const today = new Date();
  const todayIso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(
    today.getDate(),
  ).padStart(2, "0")}`;
  return task.due_date < todayIso;
}
