/** Presentation metadata and small helpers for the tasks feature. */

import type {
  Task,
  TaskAssigneeFilter,
  TaskCapability,
  TaskLabel,
  TaskLabelFilter,
  TaskPerson,
  TaskPriority,
  TaskProject,
  TaskProjectFilter,
  TaskStatus,
  TaskStatusFilter,
} from "@/types/task";

export const STATUS_ORDER: TaskStatus[] = ["todo", "in_progress", "done"];

/**
 * Whether the backend says the caller may do this to the task right now.
 *
 * Presentation only, like a workspace's `hasCapability`: it hides a control the
 * API would refuse. Who may change which task --- and what a suspended company or
 * a viewer may not --- is decided by the backend and delivered with each task.
 */
export function taskCan(task: Pick<Task, "capabilities">, capability: TaskCapability): boolean {
  return task.capabilities.includes(capability);
}

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

/** What the status filter offers: everything not done, or one status. */
export const STATUS_FILTERS: readonly TaskStatusFilter[] = ["open", ...STATUS_ORDER];

export const STATUS_FILTER_LABELS: Record<TaskStatusFilter, string> = {
  open: "Open (not done)",
  ...STATUS_LABELS,
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

// --- assignees and projects ---------------------------------------------------

/**
 * Who a task in one workspace can be assigned to, and which of them is the viewer.
 *
 * Names and ids only: the member list the API returns also carries addresses,
 * and nothing on a board needs them. The backend re-checks membership on every
 * save, so this list only decides what a picker offers.
 */
export interface AssigneeOptions {
  readonly members: readonly TaskPerson[];
  readonly viewerId: string | null;
}

/**
 * Everything a task picker in one workspace can offer: its people, its projects
 * and its labels (both alphabetical, as the API lists them). Loaded once per page.
 */
export interface TaskChoices {
  readonly assignees: AssigneeOptions;
  readonly projects: readonly TaskProject[];
  readonly labels: readonly TaskLabel[];
}

export const NO_TASK_CHOICES: TaskChoices = {
  assignees: { members: [], viewerId: null },
  projects: [],
  labels: [],
};

/** What a task created from the current view starts with. */
export interface TaskDefaults {
  readonly assigneeId?: string;
  readonly projectId?: string;
  readonly labelIds?: readonly string[];
  /** `YYYY-MM-DD`: a task added from a calendar day is due that day. */
  readonly dueDate?: string;
}

/** How an assignee reads wherever one is named. */
export function assigneeName(person: TaskPerson | null, viewerId: string | null): string {
  if (!person) return "Unassigned";
  return person.id === viewerId ? `${person.display_name} (you)` : person.display_name;
}

/** How a task's project reads wherever one is named. */
export function projectName(project: TaskProject | null): string {
  return project ? project.name : "No project";
}

/**
 * What a task created from this view should start with, so it does not vanish
 * from the filtered list it was added to: "assigned to me" creates tasks for the
 * viewer, "assigned to Ana" for Ana, a project filter files them in that project
 * and a label filter tags them with that label. "Unassigned", "no project", "no
 * labels" or no filter start empty.
 */
export function defaultsFor(
  filters: {
    assignee?: TaskAssigneeFilter;
    project?: TaskProjectFilter;
    label?: TaskLabelFilter;
  },
  viewerId: string | null,
): TaskDefaults {
  return {
    assigneeId: defaultAssignee(filters.assignee, viewerId),
    projectId: filters.project && filters.project !== "none" ? filters.project : undefined,
    labelIds: filters.label && filters.label !== "none" ? [filters.label] : undefined,
  };
}

function defaultAssignee(
  filter: TaskAssigneeFilter | undefined,
  viewerId: string | null,
): string | undefined {
  if (!filter || filter === "none") return undefined;
  if (filter === "me") return viewerId ?? undefined;
  return filter;
}
