"use client";

/**
 * Optimistic task actions with Undo, shared by the list, the board and the task
 * page.
 *
 * - **Status changes** show immediately, are sent with the version the screen
 *   had, and roll back if the API refuses. The notification offers Undo, which
 *   is simply the reverse change.
 * - **Deletes** hide the task at once and are *committed later*: when the Undo
 *   window closes or the notification is dismissed. Undo just shows it again, so
 *   nothing is ever re-created. Closing the tab inside the window cancels the
 *   delete --- the safe direction to fail in.
 *
 * A colleague's newer change (409) or a suspension that started meanwhile (403)
 * rolls the screen back to the server's truth and says why.
 */

import { useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { deleteTask, isTaskConflict, updateTask } from "@/features/tasks/api/task-mutations";
import { STATUS_LABELS } from "@/features/tasks/task-utils";
import { ApiError } from "@/lib/api/client";
import type { Task, TaskStatus } from "@/types/task";

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

export function useTaskActions(overlay?: {
  put: (task: Task) => void;
  drop: (id: string) => void;
}) {
  const router = useRouter();

  async function changeStatus(task: Task, status: TaskStatus, options: { undo?: boolean } = {}) {
    if (task.status === status) return;
    const previous = task.status;
    overlay?.put({ ...task, status });
    try {
      const saved = await updateTask(task.id, { status, version: task.version });
      overlay?.put(saved);
      if (options.undo !== false) {
        toast(`Moved to ${STATUS_LABELS[status]}`, {
          description: saved.title,
          action: {
            label: "Undo",
            onClick: () => void changeStatus(saved, previous, { undo: false }),
          },
        });
      }
      router.refresh();
    } catch (error) {
      overlay?.drop(task.id);
      explain(error, "The task could not be moved.");
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

  return { changeStatus, remove };
}
