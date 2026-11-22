"use client";

/**
 * Which tasks of a list are selected, for acting on several at once.
 *
 * The conventions people already know from mail clients and Linear, GitHub or
 * Asana lists: click a row's box to toggle it, Shift-click another to take
 * everything between, a box above the list for the whole page, Escape to let go.
 *
 * The selection only ever contains tasks that are on screen: a task deleted,
 * filtered away or left behind on another page simply drops out, so an action
 * can never reach a task the person can no longer see.
 */

import { useEffect, useState } from "react";
import type { Task } from "@/types/task";

export interface TaskSelection {
  /** The selected tasks, in the order the list shows them. */
  readonly tasks: readonly Task[];
  readonly count: number;
  readonly isSelected: (id: string) => boolean;
  /** Toggle one task; with `range`, everything between it and the last one toggled. */
  readonly toggle: (id: string, options?: { range?: boolean }) => void;
  /** Select every task on screen, or none. */
  readonly setAll: (on: boolean) => void;
  readonly clear: () => void;
  /** `true`, `false`, or `"indeterminate"` when some but not all are selected. */
  readonly allState: boolean | "indeterminate";
}

export function useTaskSelection(visible: readonly Task[]): TaskSelection {
  const [picked, setPicked] = useState<ReadonlySet<string>>(() => new Set());
  const [anchor, setAnchor] = useState<string | null>(null);

  const tasks = visible.filter((task) => picked.has(task.id));
  const count = tasks.length;

  function toggle(id: string, { range = false }: { range?: boolean } = {}) {
    const order = visible.map((task) => task.id);
    const to = order.indexOf(id);
    const from = anchor === null ? -1 : order.indexOf(anchor);
    const next = new Set(picked);
    if (range && from !== -1 && to !== -1) {
      // The range takes the state the clicked row is about to get.
      const on = !picked.has(id);
      for (const between of order.slice(Math.min(from, to), Math.max(from, to) + 1)) {
        if (on) next.add(between);
        else next.delete(between);
      }
    } else if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setPicked(next);
    setAnchor(id);
  }

  function setAll(on: boolean) {
    setPicked(on ? new Set(visible.map((task) => task.id)) : new Set());
    setAnchor(null);
  }

  function clear() {
    setAll(false);
  }

  // Escape lets go of the selection --- unless something else (a menu, a dialog)
  // used that Escape to close itself first.
  useEffect(() => {
    if (count === 0) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, [role=menu], [role=dialog]")) return;
      setPicked(new Set());
      setAnchor(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [count]);

  return {
    tasks,
    count,
    isSelected: (id) => picked.has(id),
    toggle,
    setAll,
    clear,
    allState: count === 0 ? false : count === visible.length ? true : "indeterminate",
  };
}
