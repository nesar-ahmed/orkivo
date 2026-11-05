/** Presentation metadata and small helpers for the tasks feature. */

import type { Task, TaskPriority, TaskStatus } from "@/types/task";

export const STATUS_ORDER: TaskStatus[] = ["todo", "in_progress", "done"];

/**
 * The range a due date may fall in. Mirrors `MIN_DUE_DATE` / `MAX_DUE_DATE` in
 * the backend's task schemas, so the date picker never offers a date the API
 * would refuse.
 */
export const MIN_DUE_DATE = "1970-01-01";
export const MAX_DUE_DATE = "2100-12-31";

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
};

export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
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

/**
 * A stored UTC timestamp as "Nov 5, 2026, 14:03 UTC".
 *
 * Pinned to `en-US` and UTC, like `formatAccountDate`, so the server render and
 * the hydrated client render produce the same text.
 */
export function formatTimestamp(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) return isoTimestamp;
  return `${date.toLocaleString("en-US", {
    timeZone: "UTC",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  })} UTC`;
}
