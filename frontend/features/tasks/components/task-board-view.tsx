"use client";

import {
  useState,
  type KeyboardEventHandler,
  type PointerEvent as ReactPointerEvent,
  type PointerEventHandler,
  type ReactNode,
} from "react";
import Link from "next/link";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  pointerWithin,
  rectIntersection,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type Announcements,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
  type KeyboardCoordinateGetter,
  type UniqueIdentifier,
} from "@dnd-kit/core";
import { FolderKanban, FolderX, GripVertical, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { LabelChips } from "@/features/labels/components/label-chip";
import { StatusIcon } from "@/features/tasks/components/task-icons";
import { NewTaskDialog } from "@/features/tasks/components/new-task-dialog";
import {
  AssigneeAvatar,
  BlockedChip,
  DueChip,
  PriorityChip,
  ProjectChip,
} from "@/features/tasks/components/task-meta";
import { TaskRowMenu } from "@/features/tasks/components/task-row-menu";
import {
  STATUS_LABELS,
  STATUS_ORDER,
  projectName,
  taskCan,
  type TaskChoices,
  type TaskDefaults,
} from "@/features/tasks/task-utils";
import {
  useOptimisticTasks,
  useTaskActions,
  type TaskMove,
} from "@/features/tasks/use-task-actions";
import { cn } from "@/lib/utils/cn";
import type {
  Task,
  TaskLabel,
  TaskProject,
  TaskProjectFilter,
  TaskStatus,
} from "@/types/task";

export interface BoardColumnData {
  readonly status: TaskStatus;
  readonly tasks: readonly Task[];
  /** How many tasks have this status in total (the column may show fewer). */
  readonly total: number;
  /** The list view, filtered to this status: where to see a truncated column in full. */
  readonly listHref: string;
}

/**
 * A horizontal band of status columns: the whole board, or --- grouped by project
 * --- one project's tasks (or those without a project).
 */
interface Lane {
  readonly key: string;
  /** `null` for the "No project" lane; unused on an ungrouped board. */
  readonly project: TaskProject | null;
}

/** The single lane of an ungrouped board. */
const WHOLE_BOARD = "all";
const NO_PROJECT = "none";

/** Drop targets are one lane's column: `<lane>|<status>`. */
function dropId(lane: string, status: TaskStatus): string {
  return `${lane}|${status}`;
}

function parseDropId(
  id: UniqueIdentifier | undefined,
): { lane: string; status: TaskStatus } | null {
  if (id === undefined) return null;
  const [lane, status] = String(id).split("|");
  if (!lane || !STATUS_ORDER.includes(status as TaskStatus)) return null;
  return { lane, status: status as TaskStatus };
}

/**
 * The board: one column per status. Moving a card between columns changes its
 * status, optimistically and with Undo, exactly like the status menu.
 *
 * Grouped by project, the board becomes swimlanes --- one per project, plus "No
 * project" --- each with its own status columns. Dropping a card in another lane
 * files it under that project too, as one save with one Undo; the card's menu
 * offers the same move without dragging ("Move to project").
 *
 * Drag with a pointer anywhere on a card, or with the keyboard from its handle:
 * Space picks it up, Left/Right jump between statuses, Up/Down between lanes
 * (or between columns, when the board has one lane and stacks on a phone), Space
 * drops and Escape cancels. Every step is announced. "Move to …" in each card's
 * menu is a second, non-drag way to do the same thing (keyboard, voice control,
 * switch access).
 *
 * Which cards move is each task's own `capabilities`: a member drags the tasks
 * they created or hold and sees the rest without a handle. `canCreate` is the
 * workspace's, and only decides the "+" on each column.
 */
export function TaskBoardView({
  columns,
  canCreate,
  basePath,
  workspaceId,
  shared,
  choices,
  defaults,
  grouped = false,
  projectFilter,
  listHref,
}: {
  columns: readonly BoardColumnData[];
  canCreate: boolean;
  basePath: string;
  workspaceId: string;
  shared: boolean;
  choices: TaskChoices;
  defaults: TaskDefaults;
  /** Swimlanes by project. */
  grouped?: boolean;
  /** Which project lanes the current filter can show. */
  projectFilter?: TaskProjectFilter;
  /** The grouped list: where to see every task when a column was truncated. */
  listHref: string;
}) {
  const { tasks, put, drop } = useOptimisticTasks(columns.flatMap((column) => column.tasks));
  const actions = useTaskActions({ put, drop });
  const [dragging, setDragging] = useState<Task | null>(null);

  const lanes: Lane[] = grouped
    ? projectLanes(choices.projects, tasks, projectFilter)
    : [{ key: WHOLE_BOARD, project: null }];
  const laneOf = (task: Task) => (grouped ? (task.project?.id ?? NO_PROJECT) : WHOLE_BOARD);
  const laneByKey = new Map(lanes.map((lane) => [lane.key, lane]));
  const columnLabel = (lane: string, status: TaskStatus) =>
    grouped
      ? `${projectName(laneByKey.get(lane)?.project ?? null)}, ${STATUS_LABELS[status]}`
      : STATUS_LABELS[status];

  const sensors = useSensors(
    // A small distance, so a click on the title still opens the task.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: jumpBetweenColumns(lanes.map((lane) => lane.key)),
    }),
  );

  const byId = new Map(tasks.map((task) => [task.id, task]));
  const announcements = boardAnnouncements(
    (id) => byId.get(String(id))?.title ?? "The task",
    (id) => {
      const target = parseDropId(id);
      return target ? columnLabel(target.lane, target.status) : "no column";
    },
    grouped,
  );

  function handleDragStart(event: DragStartEvent) {
    setDragging(byId.get(String(event.active.id)) ?? null);
  }

  function handleDragEnd(event: DragEndEvent) {
    setDragging(null);
    const task = byId.get(String(event.active.id));
    const target = parseDropId(event.over?.id);
    if (!task || !target) return;
    const move: TaskMove = grouped
      ? { status: target.status, project: laneByKey.get(target.lane)?.project ?? null }
      : { status: target.status };
    void actions.move(task, move);
  }

  const card = (task: Task) => (
    <BoardCard
      key={task.id}
      task={task}
      lane={laneOf(task)}
      href={`${basePath}/${task.id}`}
      showProject={!grouped}
      projects={choices.projects}
      labels={choices.labels}
      onDelete={() => actions.remove(task)}
      onMove={(target) => void actions.move(task, target)}
      onRelabel={(labels) => void actions.relabel(task, labels)}
    />
  );

  const addSlot = (lane: Lane, status: TaskStatus) =>
    canCreate ? (
      <NewTaskDialog
        workspaceId={workspaceId}
        shared={shared}
        basePath={basePath}
        defaultStatus={status}
        choices={choices}
        defaults={grouped ? { ...defaults, projectId: lane.project?.id } : defaults}
        trigger={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Add a task to ${columnLabel(lane.key, status)}`}
          >
            <Plus aria-hidden="true" />
          </Button>
        }
      />
    ) : null;

  const truncated = columns.some((column) => column.total > column.tasks.length);

  return (
    <DndContext
      id="task-board"
      sensors={sensors}
      collisionDetection={pointerThenRect}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setDragging(null)}
      accessibility={{
        announcements,
        screenReaderInstructions: {
          draggable: grouped
            ? "To move a task, press Space or Enter to pick it up. Use the Left and Right arrow keys to choose a status and the Up and Down arrow keys to choose a project, then press Space or Enter to drop it, or Escape to cancel."
            : "To move a task to another status, press Space or Enter to pick it up. Use the Left and Right arrow keys to choose a column, then press Space or Enter to drop it, or Escape to cancel.",
        },
      }}
    >
      {grouped ? (
        <div className="flex flex-col gap-6">
          {truncated ? (
            <p className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              Showing the newest 100 tasks of each status.{" "}
              <Link href={listHref} className="font-medium text-foreground underline-offset-2 hover:underline">
                See every task in the list
              </Link>
              .
            </p>
          ) : null}
          {lanes.map((lane) => {
            const laneTasks = tasks.filter((task) => laneOf(task) === lane.key);
            const headingId = `board-lane-${lane.key}`;
            return (
              <section key={lane.key} aria-labelledby={headingId} className="flex flex-col gap-2">
                <h3
                  id={headingId}
                  className="flex items-center gap-2 px-1 text-sm font-semibold text-foreground"
                >
                  {lane.project ? (
                    <FolderKanban aria-hidden="true" className="size-4 text-muted-foreground" />
                  ) : (
                    <FolderX aria-hidden="true" className="size-4 text-muted-foreground" />
                  )}
                  {projectName(lane.project)}
                  <span className="rounded-full bg-card px-1.5 text-xs font-medium text-muted-foreground ring-1 ring-border">
                    {laneTasks.length}
                  </span>
                </h3>
                <div className="grid gap-3 md:grid-cols-3">
                  {STATUS_ORDER.map((status) => {
                    const cards = laneTasks.filter((task) => task.status === status);
                    return (
                      <BoardColumn
                        key={status}
                        droppableId={dropId(lane.key, status)}
                        status={status}
                        accessibleName={columnLabel(lane.key, status)}
                        total={cards.length}
                        compact
                        addSlot={addSlot(lane, status)}
                      >
                        {cards.map(card)}
                      </BoardColumn>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {columns.map((column) => {
            const cards = tasks.filter((task) => task.status === column.status);
            // Cards moved in or out on this screen shift the server's count too.
            const stayed = column.tasks.filter((t) => byId.get(t.id)?.status === column.status);
            const moved = cards.length - stayed.length;
            const total = Math.max(column.total + moved, cards.length);
            return (
              <BoardColumn
                key={column.status}
                droppableId={dropId(WHOLE_BOARD, column.status)}
                status={column.status}
                accessibleName={STATUS_LABELS[column.status]}
                total={total}
                truncatedHref={total > cards.length ? column.listHref : undefined}
                addSlot={addSlot({ key: WHOLE_BOARD, project: null }, column.status)}
              >
                {cards.map(card)}
              </BoardColumn>
            );
          })}
        </div>
      )}

      <DragOverlay dropAnimation={null}>
        {dragging ? <CardBody task={dragging} overlay showProject={!grouped} /> : null}
      </DragOverlay>
    </DndContext>
  );
}

/**
 * The lanes a grouped board shows: every project the workspace offers, plus any
 * project a loaded task names that the (first page of the) list did not, then
 * "No project" last --- the same order as the grouped list. A project filter
 * narrows it to that one lane.
 */
function projectLanes(
  projects: readonly TaskProject[],
  tasks: readonly Task[],
  filter: TaskProjectFilter | undefined,
): Lane[] {
  if (filter === NO_PROJECT) return [{ key: NO_PROJECT, project: null }];
  const known = new Map(projects.map((project) => [project.id, project]));
  for (const task of tasks) {
    if (task.project && !known.has(task.project.id)) known.set(task.project.id, task.project);
  }
  if (filter) {
    const only = known.get(filter);
    return only ? [{ key: only.id, project: only }] : [];
  }
  return [
    ...[...known.values()].map((project) => ({ key: project.id, project })),
    { key: NO_PROJECT, project: null },
  ];
}

function BoardColumn({
  droppableId,
  status,
  accessibleName,
  total,
  truncatedHref,
  compact = false,
  addSlot,
  children,
}: {
  droppableId: string;
  status: TaskStatus;
  /** The column's name for assistive technology, including its lane on a grouped board. */
  accessibleName: string;
  total: number;
  /** Set when the column shows fewer tasks than it holds: the list shows them all. */
  truncatedHref?: string;
  /** Lanes stack many columns, so empty ones take less room there. */
  compact?: boolean;
  addSlot: ReactNode;
  children: ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: droppableId });

  return (
    <section
      ref={setNodeRef}
      aria-label={accessibleName}
      className={cn(
        "flex flex-col gap-2 rounded-xl border border-border bg-muted/40 p-2 transition-colors",
        compact ? "min-h-24" : "min-h-40",
        isOver && "border-primary/60 bg-primary/5",
      )}
    >
      <header className="flex items-center gap-2 px-1.5 pt-1">
        <StatusIcon status={status} />
        <h4 className="text-sm font-semibold text-foreground">{STATUS_LABELS[status]}</h4>
        <span className="rounded-full bg-card px-1.5 text-xs font-medium text-muted-foreground ring-1 ring-border">
          {total}
        </span>
        <span className="ml-auto">{addSlot}</span>
      </header>

      <ul aria-label={accessibleName} className="flex flex-col gap-2">
        {children}
      </ul>

      {truncatedHref ? (
        <Link
          href={truncatedHref}
          className="mt-1 rounded-md px-2 py-1.5 text-center text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          Showing the newest {total > 0 ? "100" : "0"} · see all {total} in the list
        </Link>
      ) : null}
    </section>
  );
}

function BoardCard({
  task,
  lane,
  href,
  showProject,
  projects,
  labels,
  onDelete,
  onMove,
  onRelabel,
}: {
  task: Task;
  lane: string;
  href: string;
  showProject: boolean;
  projects: readonly TaskProject[];
  labels: readonly TaskLabel[];
  onDelete: () => void;
  onMove: (target: TaskMove) => void;
  onRelabel: (labels: TaskLabel[]) => void;
}) {
  const canEdit = taskCan(task, "edit");
  const { setNodeRef, listeners, attributes, isDragging } = useDraggable({
    id: task.id,
    disabled: !canEdit,
    data: { status: task.status, lane },
  });

  // The pointer can start a drag anywhere on the card; the keyboard only from
  // the handle, which is the one focusable "draggable" --- so the card never
  // nests its links and menus inside another interactive element.
  // dnd-kit types its listeners loosely; these are the two it installs.
  const onPointerDown = listeners?.onPointerDown as PointerEventHandler<HTMLLIElement> | undefined;
  const onKeyDown = listeners?.onKeyDown as KeyboardEventHandler<HTMLButtonElement> | undefined;
  const pointerDrag = canEdit ? { onPointerDown } : {};

  return (
    <li
      ref={setNodeRef}
      {...pointerDrag}
      className={cn("touch-manipulation", isDragging && "opacity-40")}
    >
      <CardBody
        task={task}
        href={href}
        showProject={showProject}
        handle={
          canEdit ? (
            <Tooltip content="Drag, or press Space to move">
              <button
                type="button"
                {...attributes}
                onKeyDown={onKeyDown}
                aria-label={`Move ${task.title}`}
                className="-ml-1 inline-flex size-6 cursor-grab items-center justify-center rounded text-muted-foreground opacity-60 hover:bg-muted hover:opacity-100 focus-visible:opacity-100 active:cursor-grabbing"
              >
                <GripVertical aria-hidden="true" className="size-4" />
              </button>
            </Tooltip>
          ) : null
        }
        menu={
          <TaskRowMenu
            task={task}
            href={href}
            projects={projects}
            onDelete={taskCan(task, "delete") ? onDelete : undefined}
            onMove={canEdit ? (status) => onMove({ status }) : undefined}
            onMoveToProject={canEdit ? (project) => onMove({ project }) : undefined}
            labels={labels}
            onRelabel={canEdit ? onRelabel : undefined}
          />
        }
      />
    </li>
  );
}

function CardBody({
  task,
  href,
  handle,
  menu,
  overlay,
  showProject = false,
}: {
  task: Task;
  href?: string;
  handle?: ReactNode;
  menu?: ReactNode;
  overlay?: boolean;
  /** Off inside a project lane, where the lane already says it. */
  showProject?: boolean;
}) {
  return (
    <article
      className={cn(
        "group flex flex-col gap-2 rounded-lg border border-border bg-card p-3 shadow-xs transition-shadow",
        "hover:border-border-strong hover:shadow-sm",
        overlay && "rotate-1 cursor-grabbing shadow-lg ring-1 ring-primary/30",
      )}
    >
      <div className="flex items-start gap-1.5">
        {handle}
        {href ? (
          <Link
            href={href}
            onPointerDown={stop}
            className={cn(
              "min-w-0 flex-1 rounded-sm text-sm font-medium leading-snug hover:text-primary",
              task.status === "done" ? "text-muted-foreground line-through" : "text-foreground",
            )}
          >
            {task.title}
          </Link>
        ) : (
          <p className="min-w-0 flex-1 text-sm font-medium leading-snug">{task.title}</p>
        )}
        {menu ? <span onPointerDown={stop}>{menu}</span> : null}
      </div>
      {task.description ? (
        <p className="line-clamp-2 text-xs text-muted-foreground">{task.description}</p>
      ) : null}
      <LabelChips labels={task.labels} />
      <div className="flex flex-wrap items-center gap-2">
        <BlockedChip task={task} />
        <PriorityChip task={task} />
        <DueChip task={task} />
        {showProject ? <ProjectChip task={task} /> : null}
        <span className="ml-auto">{overlay ? null : <AssigneeAvatar task={task} />}</span>
      </div>
    </article>
  );
}

/** Clicks on links and menus inside a card must not start a drag. */
function stop(event: ReactPointerEvent) {
  event.stopPropagation();
}

/** Prefer what is under the pointer; fall back to overlap (keyboard dragging). */
const pointerThenRect: CollisionDetection = (args) => {
  const hits = pointerWithin(args);
  return hits.length > 0 ? hits : rectIntersection(args);
};

/**
 * Keyboard dragging moves a whole column at a time instead of a few pixels:
 * Left/Right go to the previous or next status in the same lane, Up/Down to the
 * same status in the previous or next lane. A board with a single lane has no
 * lanes to move between, so there Up/Down keep meaning "previous/next column" ---
 * the columns stack vertically on a phone.
 */
function jumpBetweenColumns(lanes: readonly string[]): KeyboardCoordinateGetter {
  return (event, { context }) => {
    const { active, collisionRect, droppableRects, over } = context;
    const step = {
      ArrowRight: [0, 1],
      ArrowLeft: [0, -1],
      ArrowDown: [1, 0],
      ArrowUp: [-1, 0],
    }[event.code];
    if (!step || !collisionRect) return undefined;
    event.preventDefault();

    // The first arrow press has no computed `over` yet: the card's own column is
    // where it stands, not the start of the board.
    const here = parseDropId(over?.id) ?? {
      lane: String(active?.data.current?.lane ?? lanes[0]),
      status: (active?.data.current?.status as TaskStatus | undefined) ?? STATUS_ORDER[0]!,
    };
    let [laneStep, statusStep] = step as [number, number];
    if (lanes.length <= 1 && laneStep !== 0) [laneStep, statusStep] = [0, laneStep];

    const clamp = (index: number, length: number) => Math.min(Math.max(index, 0), length - 1);
    const lane = lanes[clamp(lanes.indexOf(here.lane) + laneStep, lanes.length)];
    const status =
      STATUS_ORDER[clamp(STATUS_ORDER.indexOf(here.status) + statusStep, STATUS_ORDER.length)];
    const rect = lane && status ? droppableRects.get(dropId(lane, status)) : undefined;
    if (!rect) return undefined;
    return {
      x: rect.left + (rect.width - collisionRect.width) / 2,
      y: rect.top + 48,
    };
  };
}

function boardAnnouncements(
  titleOf: (id: UniqueIdentifier) => string,
  columnOf: (id: UniqueIdentifier | undefined) => string,
  grouped: boolean,
): Announcements {
  return {
    onDragStart: ({ active }) =>
      grouped
        ? `Picked up ${titleOf(active.id)}. Use the Left and Right arrow keys to choose a status, and Up and Down to choose a project.`
        : `Picked up ${titleOf(active.id)}. Use the Left and Right arrow keys to choose a column.`,
    onDragOver: ({ active, over }) => `${titleOf(active.id)} is over ${columnOf(over?.id)}.`,
    onDragEnd: ({ active, over }) =>
      over
        ? `Moved ${titleOf(active.id)} to ${columnOf(over.id)}.`
        : `${titleOf(active.id)} was dropped outside the board; nothing changed.`,
    onDragCancel: ({ active }) => `Cancelled. ${titleOf(active.id)} was not moved.`,
  };
}
