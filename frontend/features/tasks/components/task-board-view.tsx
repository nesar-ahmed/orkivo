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
} from "@dnd-kit/core";
import { GripVertical, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { StatusIcon } from "@/features/tasks/components/task-icons";
import { NewTaskDialog } from "@/features/tasks/components/new-task-dialog";
import { CreatorAvatar, DueChip, PriorityChip } from "@/features/tasks/components/task-meta";
import { TaskRowMenu } from "@/features/tasks/components/task-row-menu";
import { STATUS_LABELS, STATUS_ORDER } from "@/features/tasks/task-utils";
import { useOptimisticTasks, useTaskActions } from "@/features/tasks/use-task-actions";
import { cn } from "@/lib/utils/cn";
import type { Task, TaskStatus } from "@/types/task";

export interface BoardColumnData {
  readonly status: TaskStatus;
  readonly tasks: readonly Task[];
  /** How many tasks have this status in total (the column may show fewer). */
  readonly total: number;
  /** The list view, filtered to this status: where to see a truncated column in full. */
  readonly listHref: string;
}

/**
 * The board: one column per status. Moving a card between columns changes its
 * status, optimistically and with Undo, exactly like the status menu.
 *
 * Drag with a pointer anywhere on a card, or with the keyboard from its handle:
 * Space picks it up, Left/Right jump between columns, Space drops and Escape
 * cancels. Every step is announced. "Move to …" in each card's menu is a second,
 * non-drag way to do the same thing (keyboard, voice control, switch access).
 */
export function TaskBoardView({
  columns,
  canEdit,
  basePath,
  workspaceId,
  shared,
}: {
  columns: readonly BoardColumnData[];
  canEdit: boolean;
  basePath: string;
  workspaceId: string;
  shared: boolean;
}) {
  const { tasks, put, drop } = useOptimisticTasks(columns.flatMap((column) => column.tasks));
  const actions = useTaskActions({ put, drop });
  const [dragging, setDragging] = useState<Task | null>(null);

  const sensors = useSensors(
    // A small distance, so a click on the title still opens the task.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: jumpBetweenColumns }),
  );

  const byId = new Map(tasks.map((task) => [task.id, task]));
  const announcements = boardAnnouncements((id) => byId.get(String(id))?.title ?? "The task");

  function handleDragStart(event: DragStartEvent) {
    setDragging(byId.get(String(event.active.id)) ?? null);
  }

  function handleDragEnd(event: DragEndEvent) {
    setDragging(null);
    const task = byId.get(String(event.active.id));
    const target = event.over?.id as TaskStatus | undefined;
    if (task && target && target !== task.status) void actions.changeStatus(task, target);
  }

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
          draggable:
            "To move a task to another status, press Space or Enter to pick it up. Use the Left and Right arrow keys to choose a column, then press Space or Enter to drop it, or Escape to cancel.",
        },
      }}
    >
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
              column={column}
              total={total}
              truncated={total > cards.length}
              addSlot={
                canEdit ? (
                  <NewTaskDialog
                    workspaceId={workspaceId}
                    shared={shared}
                    basePath={basePath}
                    defaultStatus={column.status}
                    trigger={
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Add a task to ${STATUS_LABELS[column.status]}`}
                      >
                        <Plus aria-hidden="true" />
                      </Button>
                    }
                  />
                ) : null
              }
            >
              {cards.map((task) => (
                <BoardCard
                  key={task.id}
                  task={task}
                  href={`${basePath}/${task.id}`}
                  canEdit={canEdit}
                  onDelete={() => actions.remove(task)}
                  onMove={(status) => void actions.changeStatus(task, status)}
                />
              ))}
            </BoardColumn>
          );
        })}
      </div>

      <DragOverlay dropAnimation={null}>
        {dragging ? <CardBody task={dragging} overlay /> : null}
      </DragOverlay>
    </DndContext>
  );
}

function BoardColumn({
  column,
  total,
  truncated,
  addSlot,
  children,
}: {
  column: BoardColumnData;
  total: number;
  truncated: boolean;
  addSlot: ReactNode;
  children: ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.status });
  const headingId = `board-column-${column.status}`;

  return (
    <section
      ref={setNodeRef}
      aria-labelledby={headingId}
      className={cn(
        "flex min-h-40 flex-col gap-2 rounded-xl border border-border bg-muted/40 p-2 transition-colors",
        isOver && "border-primary/60 bg-primary/5",
      )}
    >
      <header className="flex items-center gap-2 px-1.5 pt-1">
        <StatusIcon status={column.status} />
        <h3 id={headingId} className="text-sm font-semibold text-foreground">
          {STATUS_LABELS[column.status]}
        </h3>
        <span className="rounded-full bg-card px-1.5 text-xs font-medium text-muted-foreground ring-1 ring-border">
          {total}
        </span>
        <span className="ml-auto">{addSlot}</span>
      </header>

      <ul aria-labelledby={headingId} className="flex flex-col gap-2">
        {children}
      </ul>

      {truncated ? (
        <Link
          href={column.listHref}
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
  href,
  canEdit,
  onDelete,
  onMove,
}: {
  task: Task;
  href: string;
  canEdit: boolean;
  onDelete: () => void;
  onMove: (status: TaskStatus) => void;
}) {
  const { setNodeRef, listeners, attributes, isDragging } = useDraggable({
    id: task.id,
    disabled: !canEdit,
    data: { status: task.status },
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
            onDelete={canEdit ? onDelete : undefined}
            onMove={canEdit ? onMove : undefined}
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
}: {
  task: Task;
  href?: string;
  handle?: ReactNode;
  menu?: ReactNode;
  overlay?: boolean;
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
      <div className="flex items-center gap-2">
        <PriorityChip task={task} />
        <DueChip task={task} />
        <span className="ml-auto">{overlay ? null : <CreatorAvatar task={task} />}</span>
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
 * Left/Right (and Up/Down, for the stacked phone layout) go to the previous or
 * next status column.
 */
const jumpBetweenColumns: KeyboardCoordinateGetter = (event, { context }) => {
  const { active, collisionRect, droppableRects, over } = context;
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.code];
  if (!step || !collisionRect) return undefined;
  event.preventDefault();

  const order = STATUS_ORDER.filter((status) => droppableRects.has(status));
  // The first arrow press has no computed `over` yet: the card's own column is
  // where it stands, not the start of the board.
  const current = over?.id ?? (active?.data.current?.status as TaskStatus | undefined);
  const from = order.indexOf(current as TaskStatus);
  const target = order[Math.min(Math.max(from + step, 0), order.length - 1)];
  const rect = target ? droppableRects.get(target) : undefined;
  if (!rect) return undefined;
  return {
    x: rect.left + (rect.width - collisionRect.width) / 2,
    y: rect.top + 48,
  };
};

function boardAnnouncements(titleOf: (id: string | number) => string): Announcements {
  const column = (id: string | number | undefined) =>
    id ? STATUS_LABELS[id as TaskStatus] ?? String(id) : "no column";
  return {
    onDragStart: ({ active }) =>
      `Picked up ${titleOf(active.id)}. Use the Left and Right arrow keys to choose a column.`,
    onDragOver: ({ active, over }) => `${titleOf(active.id)} is over ${column(over?.id)}.`,
    onDragEnd: ({ active, over }) =>
      over ? `Moved ${titleOf(active.id)} to ${column(over.id)}.` : `${titleOf(active.id)} was dropped outside the board; nothing changed.`,
    onDragCancel: ({ active }) => `Cancelled. ${titleOf(active.id)} was not moved.`,
  };
}
