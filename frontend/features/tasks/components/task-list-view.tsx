"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import { Checkbox } from "@/components/ui/checkbox";
import { FolderKanban, FolderX } from "lucide-react";
import { LabelChips } from "@/features/labels/components/label-chip";
import { BulkActionBar } from "@/features/tasks/components/bulk-action-bar";
import { StatusIcon } from "@/features/tasks/components/task-icons";
import {
  AssigneeAvatar,
  BlockedChip,
  DueChip,
  PriorityChip,
  ProjectChip,
} from "@/features/tasks/components/task-meta";
import { StatusPicker } from "@/features/tasks/components/task-pickers";
import { TaskRowMenu } from "@/features/tasks/components/task-row-menu";
import {
  STATUS_LABELS,
  projectName,
  taskCan,
  type TaskChoices,
} from "@/features/tasks/task-utils";
import { useTaskSelection } from "@/features/tasks/use-task-selection";
import {
  useOptimisticTasks,
  useTaskActions,
  type TaskMove,
} from "@/features/tasks/use-task-actions";
import { cn } from "@/lib/utils/cn";
import type { Task, TaskLabel, TaskProject } from "@/types/task";

const listStyles =
  "divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-xs";

/**
 * The list view: one compact row per task, about three times as many per screen
 * as the old cards. Status and project changes and deletes are optimistic with
 * Undo.
 *
 * `grouped` splits the page into one section per project. The API sorts the
 * page by project for it, so each project's tasks arrive together; a group that
 * continues from the previous page says so rather than pretending to start.
 *
 * What each row offers comes from that task's own `capabilities`: a member sees
 * controls on the tasks they created or hold, a viewer or a suspended company
 * none --- the same rows render without a control rather than with one that
 * would fail.
 *
 * With `bulk`, each row gets a checkbox (Shift-click takes a range), a box above
 * the list selects the whole page, and a bar appears for changing or deleting
 * the selection at once. It is offered where the caller may change content at
 * all; what each task allows is still its own `capabilities`.
 */
export function TaskListView({
  tasks: serverTasks,
  basePath,
  empty,
  projects,
  labels,
  grouped = false,
  continuesGroup = false,
  bulk,
}: {
  tasks: readonly Task[];
  basePath: string;
  empty: ReactNode;
  projects: readonly TaskProject[];
  /** The workspace's labels, offered by each row's menu. */
  labels: readonly TaskLabel[];
  grouped?: boolean;
  /** The first group on this page began on the previous one. */
  continuesGroup?: boolean;
  /** Multi-select with a bulk action bar, for the workspace the list is of. */
  bulk?: { workspaceId: string; choices: TaskChoices };
}) {
  const { tasks, put, drop } = useOptimisticTasks(serverTasks);
  const actions = useTaskActions({ put, drop });
  const selection = useTaskSelection(tasks);

  if (tasks.length === 0) return <>{empty}</>;

  const selectAll = bulk ? (
    <div className="flex items-center gap-2.5 px-2 text-xs text-muted-foreground sm:px-3">
      <Checkbox
        id="select-all-tasks"
        checked={selection.allState}
        onCheckedChange={(on) => selection.setAll(on === true)}
      />
      <label htmlFor="select-all-tasks" className="cursor-pointer select-none">
        Select all {tasks.length} on this page
      </label>
      {selection.count > 0 ? (
        // Shift needs a keyboard; a touch screen selects row by row.
        <span className="hidden sm:inline">· Shift-click to select a range</span>
      ) : null}
    </div>
  ) : null;

  const bar =
    bulk && selection.count > 0 ? (
      <BulkActionBar
        selected={selection.tasks}
        choices={bulk.choices}
        onEdit={(targets, edit) => void actions.bulkEdit(bulk.workspaceId, targets, edit)}
        onDelete={(targets) =>
          actions.bulkRemove(bulk.workspaceId, targets, { afterHide: selection.clear })
        }
        onClear={selection.clear}
      />
    ) : null;

  const row = (task: Task) => (
    <TaskRow
      key={task.id}
      task={task}
      href={`${basePath}/${task.id}`}
      projects={projects}
      labels={labels}
      showProject={!grouped}
      selection={
        bulk
          ? {
              checked: selection.isSelected(task.id),
              onToggle: (range) => selection.toggle(task.id, { range }),
            }
          : undefined
      }
      onMove={(target) => void actions.move(task, target)}
      onRelabel={(next) => void actions.relabel(task, next)}
      onDelete={() => actions.remove(task)}
    />
  );

  if (!grouped) {
    return (
      <div className="flex flex-col gap-2">
        {selectAll}
        <ul aria-label="Tasks" className={listStyles}>
          {tasks.map(row)}
        </ul>
        {bar}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {selectAll}
      {groupByProject(tasks).map((group, index) => {
        const headingId = `task-group-${group.project?.id ?? "none"}`;
        return (
          <section key={headingId} aria-labelledby={headingId} className="flex flex-col gap-2">
            <h3
              id={headingId}
              className="flex items-center gap-2 px-1 text-sm font-semibold text-foreground"
            >
              {group.project ? (
                <FolderKanban aria-hidden="true" className="size-4 text-muted-foreground" />
              ) : (
                <FolderX aria-hidden="true" className="size-4 text-muted-foreground" />
              )}
              {projectName(group.project)}
              {index === 0 && continuesGroup ? (
                <span className="text-xs font-normal text-muted-foreground">(continued)</span>
              ) : null}
              <span className="rounded-full bg-card px-1.5 text-xs font-medium text-muted-foreground ring-1 ring-border">
                {group.tasks.length}
                <span className="sr-only"> on this page</span>
              </span>
            </h3>
            <ul aria-labelledby={headingId} className={listStyles}>
              {group.tasks.map(row)}
            </ul>
          </section>
        );
      })}
      {bar}
    </div>
  );
}

function TaskRow({
  task,
  href,
  projects,
  labels,
  showProject,
  selection,
  onMove,
  onRelabel,
  onDelete,
}: {
  task: Task;
  href: string;
  projects: readonly TaskProject[];
  labels: readonly TaskLabel[];
  showProject: boolean;
  /** Present when the list is multi-select. `range` is a Shift-click. */
  selection?: { checked: boolean; onToggle: (range: boolean) => void };
  onMove: (target: TaskMove) => void;
  onRelabel: (labels: TaskLabel[]) => void;
  onDelete: () => void;
}) {
  const canEdit = taskCan(task, "edit");
  return (
    <li
      className={cn(
        "group flex items-center gap-2 px-2 py-2 transition-colors hover:bg-muted/50 sm:gap-3 sm:px-3",
        selection?.checked && "bg-primary/5 hover:bg-primary/10",
      )}
    >
      {selection ? (
        <Checkbox
          checked={selection.checked}
          aria-label={`Select ${task.title}`}
          // The click, not the state change, knows whether Shift was held.
          onClick={(event) => {
            event.preventDefault();
            selection.onToggle(event.shiftKey);
          }}
        />
      ) : null}
      {canEdit ? (
        <StatusPicker
          value={task.status}
          taskTitle={task.title}
          onChange={(status) => onMove({ status })}
        />
      ) : (
        <span className="inline-flex size-7 items-center justify-center">
          <StatusIcon status={task.status} />
          <span className="sr-only">{STATUS_LABELS[task.status]}</span>
        </span>
      )}

      <div className="min-w-0 flex-1">
        <Link
          href={href}
          className={cn(
            "block truncate rounded-sm text-sm font-medium hover:text-primary",
            task.status === "done" ? "text-muted-foreground line-through" : "text-foreground",
          )}
        >
          {task.title}
        </Link>
        {task.description ? (
          <p className="truncate text-xs text-muted-foreground">{task.description}</p>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <BlockedChip task={task} />
        {task.labels.length > 0 ? (
          <span className="hidden md:inline-flex">
            <LabelChips labels={task.labels} max={2} className="flex-nowrap" />
          </span>
        ) : null}
        {showProject ? (
          <span className="hidden sm:inline-flex">
            <ProjectChip task={task} />
          </span>
        ) : null}
        <PriorityChip task={task} compact />
        <DueChip task={task} />
        <AssigneeAvatar task={task} />
        <TaskRowMenu
          task={task}
          href={href}
          projects={projects}
          onMoveToProject={canEdit ? (project) => onMove({ project }) : undefined}
          labels={labels}
          onRelabel={canEdit ? onRelabel : undefined}
          onDelete={taskCan(task, "delete") ? onDelete : undefined}
        />
      </div>
    </li>
  );
}

/**
 * Tasks by project, each group where its first task appears. The API already
 * sends a grouped page in this order; keying by project (rather than by runs)
 * keeps it true while a task is being moved to another project on screen.
 */
function groupByProject(
  tasks: readonly Task[],
): { project: TaskProject | null; tasks: Task[] }[] {
  const groups = new Map<string, { project: TaskProject | null; tasks: Task[] }>();
  for (const task of tasks) {
    const key = task.project?.id ?? "none";
    const group = groups.get(key) ?? { project: task.project, tasks: [] };
    group.tasks.push(task);
    groups.set(key, group);
  }
  return [...groups.values()];
}
