"use client";

/**
 * Optimistic task actions with Undo, shared by the list, the board and the task
 * page.
 *
 * - **Moves** --- a new status, a new project, a new due date, or several at once
 *   (a card dropped in another lane of a grouped board, or on another day of the
 *   calendar) --- show immediately, are sent as one save with the version the
 *   screen had, and roll back if the API refuses. The notification offers Undo,
 *   which is simply the reverse change.
 * - **Relabelling** works the same way: the new set of labels shows at once, is
 *   one save, and Undo puts the previous set back.
 * - **Blocked tasks** move like any other --- dependencies are a guide, not a
 *   lock --- but starting or finishing one says it is still waiting on open work
 *   (`warnIfBlocked`).
 * - **Deletes** hide the task at once and are *committed later*: when the Undo
 *   window closes or the notification is dismissed. Undo just shows it again, so
 *   nothing is ever re-created. Closing the tab inside the window cancels the
 *   delete --- the safe direction to fail in.
 * - **Several tasks at once** (a list's selection) work the same way: one change
 *   shows on every task at once and is one bulk save, all or nothing; Undo puts
 *   each task back to exactly what it was. A bulk delete hides them all and is
 *   committed when the Undo window closes.
 *
 * A colleague's newer change (409), or a refusal that arrived meanwhile (403: a
 * suspension, or a role or holder change that took the task out of the caller's
 * hands), rolls the screen back to the server's truth and says why.
 */

import { useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { MAX_LABELS_PER_TASK, sortLabels } from "@/features/labels/label-utils";
import { shortDay } from "@/features/tasks/task-dates";
import {
  bulkDeleteTasks,
  bulkUpdateTasks,
  deleteTask,
  isTaskConflict,
  updateTask,
} from "@/features/tasks/api/task-mutations";
import { PRIORITY_LABELS, STATUS_LABELS, projectName } from "@/features/tasks/task-utils";
import { ApiError } from "@/lib/api/client";
import type {
  BulkTaskChanges,
  BulkTaskRef,
  Task,
  TaskLabel,
  TaskPerson,
  TaskPriority,
  TaskProject,
  TaskStatus,
} from "@/types/task";

/** How long Undo stays available before a delete is sent. */
export const UNDO_WINDOW_MS = 5_000;

// --- tasks deleted but not yet committed -------------------------------------
// Module-level so the state survives navigation: delete on a task's page, land
// on the board, and the task stays hidden there until the delete is committed.
let hidden: ReadonlySet<string> = new Set();
const listeners = new Set<() => void>();

function setHidden(next: ReadonlySet<string>) {
  hidden = next;
  for (const listener of listeners) listener();
}

function subscribeHidden(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const EMPTY: ReadonlySet<string> = new Set();

/** Ids of tasks that are deleted on screen, waiting for their Undo window. */
export function useHiddenTasks(): ReadonlySet<string> {
  return useSyncExternalStore(subscribeHidden, () => hidden, () => EMPTY);
}

// --- optimistic overlay --------------------------------------------------------

/**
 * The tasks to render: the server's list, minus pending deletes, with local
 * optimistic edits laid over it. An edit is dropped as soon as the server has
 * caught up (its version is at least as new), so the overlay never goes stale.
 */
export function useOptimisticTasks(serverTasks: readonly Task[]) {
  const [overlay, setOverlay] = useState<Readonly<Record<string, Task>>>({});
  const hiddenIds = useHiddenTasks();

  const tasks = serverTasks
    .filter((task) => !hiddenIds.has(task.id))
    .map((task) => {
      const local = overlay[task.id];
      return local && local.version >= task.version ? local : task;
    });

  const put = (task: Task) => setOverlay((current) => ({ ...current, [task.id]: task }));
  const drop = (id: string) =>
    setOverlay((current) => {
      const next = { ...current };
      delete next[id];
      return next;
    });

  return { tasks, put, drop };
}

// --- actions -------------------------------------------------------------------

function explain(error: unknown, fallback: string): void {
  if (isTaskConflict(error)) {
    toast.error("Someone else changed this task a moment ago", {
      description: "Showing their version now.",
    });
  } else if (error instanceof ApiError && error.status === 404) {
    toast.error("This task no longer exists", {
      description: "It was deleted, or you lost access to its workspace.",
    });
  } else if (error instanceof ApiError) {
    toast.error(fallback, { description: error.message });
  } else {
    toast.error(fallback);
  }
}

/**
 * Where a task is moved to. An omitted field stays as it is; `project: null` means
 * no project and `dueDate: null` no due date.
 */
export interface TaskMove {
  readonly status?: TaskStatus;
  readonly project?: TaskProject | null;
  /** `YYYY-MM-DD`. */
  readonly dueDate?: string | null;
}

export function useTaskActions(overlay?: {
  put: (task: Task) => void;
  drop: (id: string) => void;
}) {
  const router = useRouter();

  /** Move a task to another status, project and/or due date, as one save with Undo. */
  async function move(task: Task, target: TaskMove, options: { undo?: boolean } = {}) {
    const status = target.status ?? task.status;
    const project = target.project === undefined ? task.project : target.project;
    const dueDate = target.dueDate === undefined ? task.due_date : target.dueDate;
    const statusChanged = status !== task.status;
    const projectChanged = (project?.id ?? null) !== (task.project?.id ?? null);
    const dueChanged = dueDate !== task.due_date;
    if (!statusChanged && !projectChanged && !dueChanged) return;

    const previous: TaskMove = {
      status: task.status,
      project: task.project,
      dueDate: task.due_date,
    };
    overlay?.put({ ...task, status, project, due_date: dueDate });
    try {
      const saved = await updateTask(task.id, {
        ...(statusChanged ? { status } : {}),
        ...(projectChanged ? { project_id: project?.id ?? null } : {}),
        ...(dueChanged ? { due_date: dueDate } : {}),
        version: task.version,
      });
      overlay?.put(saved);
      if (options.undo !== false) {
        const summary = describeMove({
          status: statusChanged ? status : undefined,
          project,
          projectChanged,
          dueDate,
          dueChanged,
        });
        toast(summary, {
          description: saved.title,
          action: {
            label: "Undo",
            onClick: () => void move(saved, previous, { undo: false }),
          },
        });
        if (statusChanged) warnIfBlocked(saved, status);
      }
      router.refresh();
    } catch (error) {
      overlay?.drop(task.id);
      explain(error, "The task could not be moved.");
      router.refresh();
    }
  }

  function changeStatus(task: Task, status: TaskStatus, options: { undo?: boolean } = {}) {
    return move(task, { status }, options);
  }

  /** Give a task exactly these labels, as one save with Undo. */
  async function relabel(
    task: Task,
    labels: readonly TaskLabel[],
    options: { undo?: boolean } = {},
  ) {
    const next = sortLabels(labels);
    const added = next.filter((label) => !task.labels.some((old) => old.id === label.id));
    const removed = task.labels.filter((label) => !next.some((now) => now.id === label.id));
    if (added.length === 0 && removed.length === 0) return;

    const previous = task.labels;
    overlay?.put({ ...task, labels: next });
    try {
      const saved = await updateTask(task.id, {
        label_ids: next.map((label) => label.id),
        version: task.version,
      });
      overlay?.put(saved);
      if (options.undo !== false) {
        toast(describeRelabel(added, removed), {
          description: saved.title,
          action: {
            label: "Undo",
            onClick: () => void relabel(saved, previous, { undo: false }),
          },
        });
      }
      router.refresh();
    } catch (error) {
      overlay?.drop(task.id);
      explain(error, "The labels could not be changed.");
      router.refresh();
    }
  }

  function remove(task: Task, options: { afterHide?: () => void } = {}) {
    let settled = false;
    setHidden(new Set([...hidden, task.id]));
    options.afterHide?.();

    const restore = () => {
      const next = new Set(hidden);
      next.delete(task.id);
      setHidden(next);
    };

    const commit = async () => {
      if (settled) return;
      settled = true;
      try {
        await deleteTask(task.id, task.version);
        router.refresh();
        // Keep it hidden until the refreshed list (without it) has arrived.
        window.setTimeout(restore, 1_500);
      } catch (error) {
        restore();
        explain(error, "The task could not be deleted.");
        router.refresh();
      }
    };

    const timer = window.setTimeout(commit, UNDO_WINDOW_MS);
    toast("Task deleted", {
      description: task.title,
      duration: UNDO_WINDOW_MS,
      action: {
        label: "Undo",
        onClick: () => {
          if (settled) return;
          settled = true;
          window.clearTimeout(timer);
          restore();
        },
      },
      // Dismissing the notification means "yes, delete it": do it now.
      onDismiss: () => {
        window.clearTimeout(timer);
        void commit();
      },
    });
  }

  /**
   * Make one change to several tasks of a workspace, as one save with one Undo.
   *
   * Only the tasks it would actually change are sent --- moving three tasks to
   * Done when one already is sends two --- and each shows the change at once.
   * The save is all or nothing: if the API refuses any of them, every task goes
   * back to the server's truth and the notification says why.
   */
  async function bulkEdit(
    workspaceId: string,
    tasks: readonly Task[],
    edit: BulkEdit,
    options: { undo?: boolean } = {},
  ) {
    const targets = tasks.filter((task) => changesTask(task, edit));
    if (targets.length === 0) {
      if (options.undo !== false) toast("Nothing to change", { description: unchangedReason(edit) });
      return;
    }
    for (const task of targets) overlay?.put(predict(task, edit));
    try {
      const saved = await bulkUpdateTasks(workspaceId, targets.map(reference), bulkChanges(edit));
      for (const task of saved) overlay?.put(task);
      if (options.undo !== false) {
        toast(describeBulkEdit(edit, saved.length), {
          action: {
            label: "Undo",
            onClick: () => void undoBulkEdit(workspaceId, targets, saved, edit),
          },
        });
      }
      router.refresh();
    } catch (error) {
      for (const task of targets) overlay?.drop(task.id);
      explainBulk(error, "The tasks could not be changed.");
      router.refresh();
    }
  }

  /** Put every task back to what it was before `edit`: one save per previous value. */
  async function undoBulkEdit(
    workspaceId: string,
    before: readonly Task[],
    saved: readonly Task[],
    edit: BulkEdit,
  ) {
    const now = new Map(saved.map((task) => [task.id, task]));
    for (const group of reversal(before, edit)) {
      const current = group.ids.map((id) => now.get(id)).filter((task) => task !== undefined);
      await bulkEdit(workspaceId, current, group.edit, { undo: false });
    }
  }

  /** Delete several tasks: hidden at once, sent as one request when the Undo window closes. */
  function bulkRemove(
    workspaceId: string,
    tasks: readonly Task[],
    options: { afterHide?: () => void } = {},
  ) {
    if (tasks.length === 0) return;
    const ids = tasks.map((task) => task.id);
    let settled = false;
    setHidden(new Set([...hidden, ...ids]));
    options.afterHide?.();

    const restore = () => {
      const next = new Set(hidden);
      for (const id of ids) next.delete(id);
      setHidden(next);
    };

    const commit = async () => {
      if (settled) return;
      settled = true;
      try {
        await bulkDeleteTasks(workspaceId, tasks.map(reference));
        router.refresh();
        window.setTimeout(restore, 1_500);
      } catch (error) {
        restore();
        explainBulk(error, "The tasks could not be deleted.");
        router.refresh();
      }
    };

    const timer = window.setTimeout(commit, UNDO_WINDOW_MS);
    toast(`${tasksCount(tasks.length)} deleted`, {
      duration: UNDO_WINDOW_MS,
      action: {
        label: "Undo",
        onClick: () => {
          if (settled) return;
          settled = true;
          window.clearTimeout(timer);
          restore();
        },
      },
      onDismiss: () => {
        window.clearTimeout(timer);
        void commit();
      },
    });
  }

  return { bulkEdit, bulkRemove, changeStatus, move, relabel, remove };
}

// --- several tasks at once ------------------------------------------------------

/** One change a list's selection bar can make to every selected task. */
export type BulkEdit =
  | { readonly field: "status"; readonly value: TaskStatus }
  | { readonly field: "priority"; readonly value: TaskPriority }
  /** `YYYY-MM-DD`, or `null` for no due date. */
  | { readonly field: "due"; readonly value: string | null }
  | { readonly field: "assignee"; readonly value: TaskPerson | null }
  | { readonly field: "project"; readonly value: TaskProject | null }
  | { readonly field: "addLabel"; readonly value: TaskLabel }
  | { readonly field: "removeLabel"; readonly value: TaskLabel };

function reference(task: Task): BulkTaskRef {
  return { id: task.id, version: task.version };
}

/** Whether `edit` would change `task` at all (and whether it has room for a label). */
export function changesTask(task: Task, edit: BulkEdit): boolean {
  switch (edit.field) {
    case "status":
      return task.status !== edit.value;
    case "priority":
      return task.priority !== edit.value;
    case "due":
      return task.due_date !== edit.value;
    case "assignee":
      return (task.assignee?.id ?? null) !== (edit.value?.id ?? null);
    case "project":
      return (task.project?.id ?? null) !== (edit.value?.id ?? null);
    case "addLabel":
      return (
        !task.labels.some((label) => label.id === edit.value.id) &&
        task.labels.length < MAX_LABELS_PER_TASK
      );
    case "removeLabel":
      return task.labels.some((label) => label.id === edit.value.id);
  }
}

/** What the API is asked for. */
function bulkChanges(edit: BulkEdit): BulkTaskChanges {
  switch (edit.field) {
    case "status":
      return { status: edit.value };
    case "priority":
      return { priority: edit.value };
    case "due":
      return { due_date: edit.value };
    case "assignee":
      return { assignee_id: edit.value?.id ?? null };
    case "project":
      return { project_id: edit.value?.id ?? null };
    case "addLabel":
      return { add_label_ids: [edit.value.id] };
    case "removeLabel":
      return { remove_label_ids: [edit.value.id] };
  }
}

/** The task as it will look once saved, for showing the change at once. */
function predict(task: Task, edit: BulkEdit): Task {
  switch (edit.field) {
    case "status":
      return { ...task, status: edit.value };
    case "priority":
      return { ...task, priority: edit.value };
    case "due":
      return { ...task, due_date: edit.value };
    case "assignee":
      return { ...task, assignee: edit.value };
    case "project":
      return { ...task, project: edit.value };
    case "addLabel":
      return { ...task, labels: sortLabels([...task.labels, edit.value]) };
    case "removeLabel":
      return { ...task, labels: task.labels.filter((label) => label.id !== edit.value.id) };
  }
}

/**
 * The saves that undo `edit`: the tasks grouped by what they held before, each
 * group set back to it. A label that was added comes off the tasks it was added
 * to, and one that was removed goes back on the tasks it came off.
 */
function reversal(
  before: readonly Task[],
  edit: BulkEdit,
): { edit: BulkEdit; ids: string[] }[] {
  if (edit.field === "addLabel") {
    return [{ edit: { field: "removeLabel", value: edit.value }, ids: before.map((t) => t.id) }];
  }
  if (edit.field === "removeLabel") {
    return [{ edit: { field: "addLabel", value: edit.value }, ids: before.map((t) => t.id) }];
  }
  const groups = new Map<string, { edit: BulkEdit; ids: string[] }>();
  for (const task of before) {
    const previous = previousValue(task, edit.field);
    const key = JSON.stringify(previous.value);
    const group = groups.get(key) ?? { edit: previous, ids: [] };
    group.ids.push(task.id);
    groups.set(key, group);
  }
  return [...groups.values()];
}

function previousValue(
  task: Task,
  field: "status" | "priority" | "due" | "assignee" | "project",
): BulkEdit {
  switch (field) {
    case "status":
      return { field, value: task.status };
    case "priority":
      return { field, value: task.priority };
    case "due":
      return { field, value: task.due_date };
    case "assignee":
      return { field, value: task.assignee };
    case "project":
      return { field, value: task.project };
  }
}

function tasksCount(count: number): string {
  return `${count} ${count === 1 ? "task" : "tasks"}`;
}

/** "Moved 3 tasks to Done", "Added Bug to 2 tasks", "Unassigned 4 tasks". */
export function describeBulkEdit(edit: BulkEdit, count: number): string {
  const tasks = tasksCount(count);
  switch (edit.field) {
    case "status":
      return `Moved ${tasks} to ${STATUS_LABELS[edit.value]}`;
    case "priority":
      return `Set ${tasks} to ${PRIORITY_LABELS[edit.value]} priority`;
    case "due":
      return edit.value
        ? `Rescheduled ${tasks} to ${shortDay(edit.value)}`
        : `Removed the due date from ${tasks}`;
    case "assignee":
      return edit.value ? `Assigned ${tasks} to ${edit.value.display_name}` : `Unassigned ${tasks}`;
    case "project":
      return edit.value
        ? `Moved ${tasks} to ${edit.value.name}`
        : `Took ${tasks} out of their project`;
    case "addLabel":
      return `Added ${edit.value.name} to ${tasks}`;
    case "removeLabel":
      return `Removed ${edit.value.name} from ${tasks}`;
  }
}

function unchangedReason(edit: BulkEdit): string {
  return edit.field === "addLabel"
    ? `Every selected task already carries ${edit.value.name}, or has no room for another label.`
    : "Every selected task already has that value.";
}

/** A bulk refusal, in words: the API names what happened; nothing was changed. */
function explainBulk(error: unknown, fallback: string): void {
  if (error instanceof ApiError && error.code === "TASK_CONFLICT") {
    toast.error("Someone else changed some of these tasks a moment ago", {
      description: "Nothing was changed. Showing the latest versions now.",
    });
  } else if (error instanceof ApiError && error.status === 404) {
    toast.error("Some of these tasks no longer exist", {
      description: "Nothing was changed. They were deleted, or you lost access to them.",
    });
  } else if (error instanceof ApiError) {
    toast.error(fallback, { description: error.message });
  } else {
    toast.error(fallback);
  }
}

/**
 * Say so when work is started or finished while tasks it waits on are still open.
 * The change is already saved: this is a heads-up, never a refusal.
 */
export function warnIfBlocked(task: Task, status: TaskStatus): void {
  const count = task.open_blocker_count;
  if (status === "todo" || count === 0) return;
  toast.warning(`Still waiting on ${count} open ${count === 1 ? "task" : "tasks"}`, {
    description: `${task.title} was moved to ${STATUS_LABELS[status]} anyway.`,
  });
}

/** "Moved to Website · Done", "Rescheduled to Nov 12" or "Due date removed". */
function describeMove({
  status,
  project,
  projectChanged,
  dueDate,
  dueChanged,
}: {
  status?: TaskStatus;
  project: TaskProject | null;
  projectChanged: boolean;
  dueDate: string | null;
  dueChanged: boolean;
}): string {
  const where = [
    projectChanged ? projectName(project) : null,
    status ? STATUS_LABELS[status] : null,
  ].filter(Boolean);
  const when = dueChanged
    ? dueDate
      ? `Rescheduled to ${shortDay(dueDate)}`
      : "Due date removed"
    : null;
  if (where.length === 0) return when ?? "Moved";
  return [`Moved to ${where.join(" · ")}`, when].filter(Boolean).join(" · ");
}

/** "Added Bug", "Removed Docs", or both. */
function describeRelabel(added: readonly TaskLabel[], removed: readonly TaskLabel[]): string {
  const names = (labels: readonly TaskLabel[]) => labels.map((label) => label.name).join(", ");
  return [
    added.length > 0 ? `Added ${names(added)}` : null,
    removed.length > 0 ? `Removed ${names(removed)}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}
