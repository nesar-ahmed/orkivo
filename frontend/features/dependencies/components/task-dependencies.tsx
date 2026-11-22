"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Ban, Plus, Search, Workflow, X } from "lucide-react";
import { toast } from "sonner";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { fetchDependencies } from "@/features/dependencies/api/dependency-queries";
import { addBlocker, removeBlocker } from "@/features/dependencies/api/dependency-mutations";
import type { TaskDependenciesData } from "@/features/dependencies/api/task-dependencies-data";
import { fetchTasks } from "@/features/tasks/api/task-queries";
import { StatusIcon } from "@/features/tasks/components/task-icons";
import { STATUS_LABELS, formatDueDate, taskCan } from "@/features/tasks/task-utils";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";
import type { DependencyTask, TaskDependencies } from "@/types/dependency";
import type { Task } from "@/types/task";

const NONE: TaskDependencies = { blocked_by: [], blocking: [] };
const SEARCH_DEBOUNCE_MS = 250;
const RESULTS = 10;

/** Which side of the task a link is on. */
type Direction = "blocked_by" | "blocking";

/**
 * A task's dependencies, both ways: what it waits on ("Blocked by") and what
 * waits on it ("Blocking"), each with the way to add and remove links.
 *
 * A link is always written from the waiting task's side, so adding to "Blocking"
 * makes the *other* task wait on this one. Both lists come from one read, open
 * work first. The API refuses a link from another workspace, to the task itself,
 * made twice or closing a loop, and says why in words meant for people, which is
 * what the notification shows. Removing offers Undo, like the rest of the product.
 *
 * Dependencies are a guide, not a lock: while this task waits on open work it
 * says so, but it can still be started or finished.
 *
 * A link belongs to the task that waits, so changing one takes the right to
 * change *that* task: "Blocked by" follows this task's `edit` (`canEdit`), and
 * each "Blocking" row follows the other task's own `capabilities` --- its picker
 * offers only tasks the caller may change. `canLink` is the workspace's
 * `edit_content`: without it (a viewer, view mode) nothing is offered at all.
 */
export function TaskDependenciesSection({
  taskId,
  workspaceId,
  basePath,
  canEdit,
  canLink,
  data,
}: {
  taskId: string;
  workspaceId: string;
  /** The workspace's tasks page; a task's own page is below it. */
  basePath: string;
  /** This task's own `edit` capability. */
  canEdit: boolean;
  canLink: boolean;
  data: TaskDependenciesData;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [dependencies, setDependencies] = useState<TaskDependencies>(data.dependencies ?? NONE);
  const [synced, setSynced] = useState(data.dependencies);

  // A refreshed server render brought newer links: show them.
  if (data.dependencies !== synced) {
    setSynced(data.dependencies);
    setDependencies(data.dependencies ?? NONE);
  }

  const openBlockers = dependencies.blocked_by.filter((task) => task.status !== "done").length;
  const linked = new Set([
    taskId,
    ...dependencies.blocked_by.map((task) => task.id),
    ...dependencies.blocking.map((task) => task.id),
  ]);

  function fail(error: unknown, fallback: string) {
    toast.error(fallback, { description: error instanceof ApiError ? error.message : undefined });
    router.refresh();
  }

  function add(direction: Direction, other: Pick<Task, "id" | "title">) {
    startTransition(async () => {
      try {
        const next =
          direction === "blocked_by"
            ? await addBlocker(taskId, other.id)
            : await addBlocker(other.id, taskId).then(() => fetchDependencies(taskId));
        setDependencies(next);
        toast(direction === "blocked_by" ? "Now blocked by" : "Now blocking", {
          description: other.title,
        });
        router.refresh();
      } catch (error) {
        fail(error, "The dependency could not be added.");
      }
    });
  }

  function remove(direction: Direction, other: DependencyTask, options: { undo?: boolean } = {}) {
    startTransition(async () => {
      try {
        if (direction === "blocked_by") await removeBlocker(taskId, other.id);
        else await removeBlocker(other.id, taskId);
        setDependencies((current) => ({
          ...current,
          [direction]: current[direction].filter((task) => task.id !== other.id),
        }));
        if (options.undo !== false) {
          toast(direction === "blocked_by" ? "No longer blocked by" : "No longer blocking", {
            description: other.title,
            action: { label: "Undo", onClick: () => add(direction, other) },
          });
        }
        router.refresh();
      } catch (error) {
        fail(error, "The dependency could not be removed.");
      }
    });
  }

  return (
    <section
      id="dependencies"
      aria-labelledby="dependencies-heading"
      aria-busy={isPending}
      className="flex flex-col gap-3"
    >
      <h2 id="dependencies-heading" className="flex items-center gap-2 text-sm font-semibold">
        <Workflow aria-hidden="true" className="size-4 text-muted-foreground" />
        Dependencies
      </h2>

      {data.loadError ? (
        <p role="alert" className="text-sm text-danger">
          {data.loadError}
        </p>
      ) : null}

      {openBlockers > 0 ? (
        <p
          role="status"
          className="flex gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning"
        >
          <Ban aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>
            Waiting on {openBlockers} open {openBlockers === 1 ? "task" : "tasks"}. It can still
            be started or finished: dependencies are a guide, not a lock.
          </span>
        </p>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        {(["blocked_by", "blocking"] as const).map((direction) => (
          <DependencyList
            key={direction}
            direction={direction}
            tasks={dependencies[direction]}
            basePath={basePath}
            canRemove={(task) =>
              direction === "blocked_by" ? canEdit : canLink && taskCan(task, "edit")
            }
            disabled={isPending}
            onRemove={(task) => remove(direction, task)}
            picker={
              (direction === "blocked_by" ? canEdit : canLink) ? (
                <DependencyPicker
                  direction={direction}
                  workspaceId={workspaceId}
                  exclude={linked}
                  disabled={isPending}
                  onPick={(task) => add(direction, task)}
                />
              ) : null
            }
          />
        ))}
      </div>
    </section>
  );
}

const LIST_TITLES: Record<Direction, string> = { blocked_by: "Blocked by", blocking: "Blocking" };
const LIST_EMPTY: Record<Direction, string> = {
  blocked_by: "Nothing has to happen first.",
  blocking: "Nothing is waiting on this task.",
};

function DependencyList({
  direction,
  tasks,
  basePath,
  canRemove,
  disabled,
  onRemove,
  picker,
}: {
  direction: Direction;
  tasks: readonly DependencyTask[];
  basePath: string;
  canRemove: (task: DependencyTask) => boolean;
  disabled: boolean;
  onRemove: (task: DependencyTask) => void;
  picker: React.ReactNode;
}) {
  const headingId = `dependencies-${direction}`;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <h3 id={headingId} className="text-xs font-medium text-muted-foreground">
          {LIST_TITLES[direction]}
        </h3>
        <span className="rounded-full bg-card px-1.5 text-xs font-medium text-muted-foreground ring-1 ring-border">
          {tasks.length}
        </span>
        <span className="ml-auto">{picker}</span>
      </div>
      {tasks.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-3 py-2.5 text-xs text-muted-foreground">
          {LIST_EMPTY[direction]}
        </p>
      ) : (
        <ul
          aria-labelledby={headingId}
          className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card shadow-xs"
        >
          {tasks.map((task) => (
            <li key={task.id} className="flex items-center gap-2 px-2.5 py-2">
              <StatusIcon status={task.status} />
              <span className="sr-only">{STATUS_LABELS[task.status]}: </span>
              <Link
                href={`${basePath}/${task.id}`}
                className={cn(
                  "min-w-0 flex-1 truncate text-sm font-medium hover:text-primary",
                  task.status === "done" ? "text-muted-foreground line-through" : "text-foreground",
                )}
              >
                {task.title}
              </Link>
              {task.due_date ? (
                <span className="shrink-0 text-xs text-muted-foreground">
                  <span className="sr-only">Due </span>
                  {formatDueDate(task.due_date)}
                </span>
              ) : null}
              {task.assignee ? (
                <Avatar
                  name={task.assignee.display_name}
                  seed={task.assignee.id}
                  size="xs"
                  label={`Assigned to ${task.assignee.display_name}`}
                />
              ) : null}
              {canRemove(task) ? (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="size-6"
                  onClick={() => onRemove(task)}
                  disabled={disabled}
                  aria-label={`Remove ${task.title} from ${LIST_TITLES[direction].toLowerCase()}`}
                >
                  <X aria-hidden="true" />
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Find a task of the same workspace to link, by title. Searches as you type; the
 * task itself and tasks already linked either way are not offered, and for
 * "Blocking" --- which makes the picked task wait --- neither are tasks the caller
 * may not change.
 */
function DependencyPicker({
  direction,
  workspaceId,
  exclude,
  disabled,
  onPick,
}: {
  direction: Direction;
  workspaceId: string;
  exclude: ReadonlySet<string>;
  disabled: boolean;
  onPick: (task: Task) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<{ query: string; tasks: Task[] } | null>(null);
  const inputId = `dependency-search-${direction}`;

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      const search = query.trim() || undefined;
      const tasks = await fetchTasks(workspaceId, { search, page_size: RESULTS + exclude.size })
        .then((page) => page.items)
        .catch(() => []);
      if (!cancelled) setFound({ query, tasks });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [open, query, workspaceId, exclude.size]);

  const loading = found === null || found.query !== query;
  const offered = (found?.tasks ?? [])
    .filter((task) => !exclude.has(task.id))
    .filter((task) => direction === "blocked_by" || taskCan(task, "edit"))
    .slice(0, RESULTS);

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setQuery("");
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="ghost" size="xs" disabled={disabled}>
          <Plus aria-hidden="true" />
          Add
          <span className="sr-only">
            {direction === "blocked_by" ? " a task this one waits on" : " a task waiting on this one"}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-2">
        <label htmlFor={inputId} className="sr-only">
          Find a task in this workspace
        </label>
        <div className="relative">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <input
            id={inputId}
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Find a task…"
            maxLength={200}
            className="h-8 w-full rounded-md border border-border bg-card pr-2 pl-8 text-sm focus-visible:border-primary focus-visible:outline-none"
          />
        </div>
        <div aria-live="polite" className="mt-2">
          {loading ? (
            <p className="px-1 py-2 text-xs text-muted-foreground">Searching…</p>
          ) : offered.length === 0 ? (
            <p className="px-1 py-2 text-xs text-muted-foreground">
              {direction === "blocked_by"
                ? "No other tasks match."
                : "No other task you can change matches."}
            </p>
          ) : (
            <ul className="flex max-h-64 flex-col overflow-y-auto">
              {offered.map((task) => (
                <li key={task.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setOpen(false);
                      setQuery("");
                      onPick(task);
                    }}
                    className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
                  >
                    <StatusIcon status={task.status} />
                    <span className="sr-only">{STATUS_LABELS[task.status]}: </span>
                    <span className="min-w-0 flex-1 truncate">{task.title}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
