"use client";

import { useState, type PointerEvent as ReactPointerEvent, type PointerEventHandler } from "react";
import Link from "next/link";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  pointerWithin,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type DragStartEvent,
  type UniqueIdentifier,
} from "@dnd-kit/core";
import {
  ArrowLeft,
  ArrowRight,
  Ban,
  CalendarClock,
  CalendarX,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Link2,
  MoreHorizontal,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { CalendarData } from "@/features/tasks/api/task-calendar-data";
import { MAX_CALENDAR_TASKS } from "@/features/tasks/api/task-calendar-data";
import { NewTaskDialog } from "@/features/tasks/components/new-task-dialog";
import { PriorityIcon, StatusIcon } from "@/features/tasks/components/task-icons";
import { copyTaskLink } from "@/features/tasks/components/task-row-menu";
import {
  WEEKDAY_LABELS,
  addDays,
  dayTitle,
  isIsoDate,
  monthGrid,
  monthOf,
  monthTitle,
  shortDay,
} from "@/features/tasks/task-dates";
import {
  STATUS_LABELS,
  taskCan,
  type TaskChoices,
  type TaskDefaults,
} from "@/features/tasks/task-utils";
import { useOptimisticTasks, useTaskActions } from "@/features/tasks/use-task-actions";
import { useToday } from "@/features/tasks/use-today";
import { WorkspaceMark } from "@/features/workspaces/components/workspace-switcher";
import { hasCapability, taskPath, workspacePath } from "@/features/workspaces/workspace-utils";
import { cn } from "@/lib/utils/cn";
import type { Task } from "@/types/task";
import type { Workspace } from "@/types/workspace";

/**
 * Whose calendar this is. A workspace's shows its own tasks, and may offer "+" on
 * each day when its capabilities allow adding; a person's own spans their
 * workspaces, so each task links to the workspace it lives in --- and a task
 * added from a day goes into their private workspace. Either way, whether a task
 * can be moved is that task's own `capabilities`.
 */
export type CalendarScope =
  | {
      readonly kind: "workspace";
      readonly workspaceId: string;
      readonly basePath: string;
      readonly canCreate: boolean;
      readonly shared: boolean;
      readonly choices: TaskChoices;
      readonly defaults: TaskDefaults;
    }
  | {
      readonly kind: "mine";
      readonly workspaces: readonly Workspace[];
      readonly personal: Workspace | null;
      readonly choices: TaskChoices;
    };

/** Where one task lives, for its link, its controls and its workspace mark. */
interface Placement {
  readonly href: string;
  readonly canEdit: boolean;
  /** Shown on a person's own calendar only. */
  readonly workspace: Workspace | null;
}

/** The drop target that clears a due date. Never a date, so never a day's id. */
const UNSCHEDULED = "unscheduled";
/** How many tasks a day shows before the rest go behind "+N more". */
const SHOWN_PER_DAY = 3;

/**
 * A month of tasks by due date, with the tasks that have none beside it.
 *
 * Drag a task to another day to reschedule it, or onto "No due date" to clear its
 * date; each move is optimistic, one save with the version on screen, and offers
 * Undo, exactly like moving a card on the board. Every task's "⋯" menu offers the
 * same moves without dragging --- a day earlier or later, a week later, or no due
 * date --- for keyboard, voice control and switch access. "+" on a day adds a task
 * due that day.
 *
 * "Today" is the viewer's own day (`useToday`), highlighted once the page is in
 * the browser. Days outside the month are shown, dimmed, so every week is whole.
 */
export function TaskCalendar({
  data,
  scope,
  previousHref,
  nextHref,
  todayHref,
}: {
  data: CalendarData;
  scope: CalendarScope;
  previousHref: string;
  nextHref: string;
  todayHref: string;
}) {
  const { tasks, put, drop } = useOptimisticTasks([...data.tasks, ...data.unscheduled]);
  const actions = useTaskActions({ put, drop });
  const today = useToday();
  const [dragging, setDragging] = useState<Task | null>(null);
  const grid = monthGrid(data.month);
  const sensors = useSensors(
    // A small distance, so a click on a title still opens the task.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );

  const workspaces = new Map(
    scope.kind === "mine" ? scope.workspaces.map((workspace) => [workspace.id, workspace]) : [],
  );
  const place = (task: Task): Placement => {
    const canEdit = taskCan(task, "edit");
    if (scope.kind === "workspace") {
      return { href: `${scope.basePath}/${task.id}`, canEdit, workspace: null };
    }
    const workspace = workspaces.get(task.workspace_id) ?? null;
    return {
      href: workspace ? taskPath(workspace, task.id) : "/app/workspaces",
      canEdit,
      workspace,
    };
  };

  const byId = new Map(tasks.map((task) => [task.id, task]));
  const byDay = new Map<string, Task[]>();
  const unscheduled: Task[] = [];
  for (const task of tasks) {
    if (!task.due_date) unscheduled.push(task);
    // A task moved out of the weeks on screen simply leaves them.
    else if (task.due_date >= grid.first && task.due_date <= grid.last) {
      byDay.set(task.due_date, [...(byDay.get(task.due_date) ?? []), task]);
    }
  }
  const dueOnScreen = tasks.length - unscheduled.length;
  const hiddenByLimit = Math.max(data.total - data.tasks.length, 0);

  const reschedule = (task: Task, dueDate: string | null) => void actions.move(task, { dueDate });
  const targetName = (id: UniqueIdentifier | undefined) => {
    const target = String(id ?? "");
    if (target === UNSCHEDULED) return "No due date";
    return isIsoDate(target) ? dayTitle(target) : "nowhere";
  };

  function handleDragStart(event: DragStartEvent) {
    setDragging(byId.get(String(event.active.id)) ?? null);
  }

  function handleDragEnd(event: DragEndEvent) {
    setDragging(null);
    const task = byId.get(String(event.active.id));
    const target = event.over ? String(event.over.id) : null;
    if (!task || target === null) return;
    if (target === UNSCHEDULED) reschedule(task, null);
    else if (isIsoDate(target)) reschedule(task, target);
  }

  const titleOf = (id: UniqueIdentifier) => byId.get(String(id))?.title ?? "The task";
  const announcements: Announcements = {
    onDragStart: ({ active }) => `Picked up ${titleOf(active.id)}.`,
    onDragOver: ({ active, over }) =>
      over ? `${titleOf(active.id)} is over ${targetName(over.id)}.` : `${titleOf(active.id)} is over no day.`,
    onDragEnd: ({ active, over }) =>
      over
        ? `${titleOf(active.id)} was moved to ${targetName(over.id)}.`
        : `${titleOf(active.id)} was dropped and stays where it was.`,
    onDragCancel: ({ active }) => `Moving was cancelled. ${titleOf(active.id)} stays where it was.`,
  };

  const addSlot = (day: string) => {
    if (scope.kind === "workspace") {
      if (!scope.canCreate) return null;
      return (
        <NewTaskDialog
          workspaceId={scope.workspaceId}
          shared={scope.shared}
          basePath={scope.basePath}
          choices={scope.choices}
          defaults={{ ...scope.defaults, dueDate: day }}
          trigger={<AddButton day={day} />}
        />
      );
    }
    const personal = scope.personal;
    if (!personal || !hasCapability(personal, "edit_content")) return null;
    return (
      <NewTaskDialog
        workspaceId={personal.id}
        shared={false}
        basePath={workspacePath(personal, "tasks")}
        choices={scope.choices}
        defaults={{ dueDate: day }}
        trigger={<AddButton day={day} />}
      />
    );
  };

  return (
    <DndContext
      id="task-calendar"
      sensors={sensors}
      collisionDetection={pointerWithin}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setDragging(null)}
      accessibility={{
        announcements,
        screenReaderInstructions: {
          draggable:
            "To reschedule a task without dragging, open its actions menu and choose another day, or remove its due date.",
        },
      }}
    >
      {/* The tray sits beside the grid only where the grid can spare the room. */}
      <div className="flex flex-col gap-4 2xl:flex-row 2xl:items-start">
        <section aria-labelledby="calendar-title" className="flex min-w-0 flex-1 flex-col gap-3">
          <header className="flex flex-wrap items-center gap-2">
            <h3 id="calendar-title" className="text-base font-semibold tracking-tight">
              {monthTitle(data.month)}
            </h3>
            <span className="text-xs text-muted-foreground">
              {dueOnScreen} {dueOnScreen === 1 ? "task" : "tasks"} due
            </span>
            <nav aria-label="Months" className="ml-auto flex items-center gap-1">
              <ButtonLink href={previousHref} size="icon-sm" aria-label="Previous month">
                <ChevronLeft aria-hidden="true" />
              </ButtonLink>
              <ButtonLink href={todayHref} aria-current={monthOf(today) === data.month ? "date" : undefined}>
                Today
              </ButtonLink>
              <ButtonLink href={nextHref} size="icon-sm" aria-label="Next month">
                <ChevronRight aria-hidden="true" />
              </ButtonLink>
            </nav>
          </header>

          {hiddenByLimit > 0 ? (
            <p role="status" className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              Showing the first {MAX_CALENDAR_TASKS} of {data.total} tasks due in these weeks.
              Narrow the filters to see the rest.
            </p>
          ) : null}

          <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-xs">
            <div className="min-w-[44rem]">
              <div aria-hidden="true" className="grid grid-cols-7 border-b border-border">
                {WEEKDAY_LABELS.map((weekday) => (
                  <div
                    key={weekday}
                    className="px-2 py-1.5 text-[0.7rem] font-medium tracking-wide text-muted-foreground uppercase"
                  >
                    {weekday}
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-7">
                {grid.days.map((day) => (
                  <CalendarDay
                    key={day}
                    day={day}
                    tasks={byDay.get(day) ?? []}
                    inMonth={monthOf(day) === data.month}
                    isToday={day === today}
                    today={today}
                    place={place}
                    onReschedule={reschedule}
                    addSlot={addSlot(day)}
                  />
                ))}
              </div>
            </div>
          </div>
        </section>

        <UnscheduledTray
          tasks={unscheduled}
          total={data.unscheduledTotal - data.unscheduled.length + unscheduled.length}
          dragging={dragging !== null}
          today={today}
          place={place}
          onReschedule={reschedule}
        />
      </div>

      <DragOverlay dropAnimation={null}>
        {dragging ? (
          <ChipBody task={dragging} placement={place(dragging)} overlay />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

function AddButton({ day, ...props }: { day: string }) {
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={`Add a task due ${dayTitle(day)}`}
      className="size-6 opacity-0 group-hover/day:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100 [@media(hover:none)]:opacity-100"
      {...props}
    >
      <Plus aria-hidden="true" />
    </Button>
  );
}

function CalendarDay({
  day,
  tasks,
  inMonth,
  isToday,
  today,
  place,
  onReschedule,
  addSlot,
}: {
  day: string;
  tasks: readonly Task[];
  inMonth: boolean;
  isToday: boolean;
  today: string;
  place: (task: Task) => Placement;
  onReschedule: (task: Task, dueDate: string | null) => void;
  addSlot: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: day });
  const shown = tasks.slice(0, SHOWN_PER_DAY);
  const rest = tasks.length - shown.length;
  const name = `${dayTitle(day)}${isToday ? ", today" : ""}, ${tasks.length} ${
    tasks.length === 1 ? "task" : "tasks"
  }`;

  return (
    <div
      ref={setNodeRef}
      role="group"
      aria-label={name}
      className={cn(
        "group/day flex min-h-28 flex-col gap-1 border-r border-b border-border p-1.5 transition-colors",
        "[&:nth-child(7n)]:border-r-0",
        !inMonth && "bg-muted/40",
        isOver && "bg-primary/5 ring-2 ring-primary/40 ring-inset",
      )}
    >
      <div className="flex items-center justify-between">
        <span
          className={cn(
            "inline-flex size-6 items-center justify-center rounded-full text-xs font-medium",
            isToday
              ? "bg-primary text-primary-foreground"
              : inMonth
                ? "text-foreground"
                : "text-muted-foreground",
          )}
        >
          {Number(day.slice(8))}
        </span>
        {addSlot}
      </div>
      {shown.length > 0 ? (
        <ul className="flex flex-col gap-1">
          {shown.map((task) => (
            <CalendarChip
              key={task.id}
              task={task}
              placement={place(task)}
              today={today}
              onReschedule={onReschedule}
            />
          ))}
        </ul>
      ) : null}
      {rest > 0 ? (
        <Popover>
          <PopoverTrigger className="rounded px-1 text-left text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground">
            +{rest} more<span className="sr-only"> due {dayTitle(day)}</span>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-72 p-2">
            <p className="px-1 pb-1.5 text-xs font-semibold text-foreground">{dayTitle(day)}</p>
            <ul className="flex max-h-72 flex-col gap-1 overflow-y-auto">
              {tasks.map((task) => (
                <li key={task.id}>
                  <ChipBody
                    task={task}
                    placement={place(task)}
                    menu={
                      <ChipMenu
                        task={task}
                        placement={place(task)}
                        today={today}
                        onReschedule={onReschedule}
                      />
                    }
                  />
                </li>
              ))}
            </ul>
          </PopoverContent>
        </Popover>
      ) : null}
    </div>
  );
}

function UnscheduledTray({
  tasks,
  total,
  dragging,
  today,
  place,
  onReschedule,
}: {
  tasks: readonly Task[];
  total: number;
  dragging: boolean;
  today: string;
  place: (task: Task) => Placement;
  onReschedule: (task: Task, dueDate: string | null) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: UNSCHEDULED });

  return (
    <aside
      ref={setNodeRef}
      aria-labelledby="calendar-unscheduled"
      className={cn(
        "flex flex-col gap-2 rounded-xl border border-border bg-muted/40 p-2 transition-colors 2xl:w-64 2xl:shrink-0",
        isOver && "border-primary/60 bg-primary/5",
      )}
    >
      <h3 id="calendar-unscheduled" className="flex items-center gap-2 px-1.5 pt-1 text-sm font-semibold">
        <CalendarX aria-hidden="true" className="size-4 text-muted-foreground" />
        No due date
        <span className="rounded-full bg-card px-1.5 text-xs font-medium text-muted-foreground ring-1 ring-border">
          {total}
        </span>
      </h3>
      <p className="px-1.5 text-xs text-muted-foreground">
        {dragging ? "Drop here to remove the due date." : "Drag a task onto a day to schedule it."}
      </p>
      {tasks.length > 0 ? (
        <ul className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-1">
          {tasks.map((task) => (
            <CalendarChip
              key={task.id}
              task={task}
              placement={place(task)}
              today={today}
              onReschedule={onReschedule}
            />
          ))}
        </ul>
      ) : (
        <p className="px-1.5 pb-1 text-xs text-muted-foreground">Every task here has a due date.</p>
      )}
      {total > tasks.length ? (
        <p className="px-1.5 pb-1 text-xs text-muted-foreground">
          Showing the newest {tasks.length} of {total}.
        </p>
      ) : null}
    </aside>
  );
}

function CalendarChip({
  task,
  placement,
  today,
  onReschedule,
}: {
  task: Task;
  placement: Placement;
  today: string;
  onReschedule: (task: Task, dueDate: string | null) => void;
}) {
  const { setNodeRef, listeners, isDragging } = useDraggable({
    id: task.id,
    disabled: !placement.canEdit,
  });
  // Pointer only: the keyboard path is the menu, whose moves are announced by name.
  const onPointerDown = listeners?.onPointerDown as PointerEventHandler<HTMLLIElement> | undefined;

  return (
    <li
      ref={setNodeRef}
      onPointerDown={placement.canEdit ? onPointerDown : undefined}
      className={cn("touch-manipulation", isDragging && "opacity-40")}
    >
      <ChipBody
        task={task}
        placement={placement}
        menu={
          <ChipMenu task={task} placement={placement} today={today} onReschedule={onReschedule} />
        }
      />
    </li>
  );
}

function ChipBody({
  task,
  placement,
  menu,
  overlay = false,
}: {
  task: Task;
  placement: Placement;
  menu?: React.ReactNode;
  overlay?: boolean;
}) {
  return (
    <div
      className={cn(
        "group/chip relative flex min-w-0 items-center gap-1 rounded-md border border-border bg-card px-1.5 py-1 text-xs shadow-xs",
        "hover:border-border-strong",
        placement.canEdit && "cursor-grab active:cursor-grabbing",
        overlay && "w-48 rotate-1 shadow-lg ring-1 ring-primary/30",
      )}
    >
      <StatusIcon status={task.status} className="size-3.5" />
      <span className="sr-only">{STATUS_LABELS[task.status]}: </span>
      {placement.workspace ? (
        <WorkspaceMark workspace={placement.workspace} className="size-3.5 rounded-sm text-[0.5rem]" />
      ) : null}
      <Link
        href={placement.href}
        // Links are natively draggable; that would fight the calendar's own drag.
        draggable={false}
        className={cn(
          "min-w-0 flex-1 truncate rounded-sm font-medium hover:text-primary",
          task.status === "done" ? "text-muted-foreground line-through" : "text-foreground",
        )}
      >
        {task.title}
      </Link>
      {task.open_blocker_count > 0 ? (
        <>
          <Ban aria-hidden="true" className="size-3.5 shrink-0 text-warning" />
          <span className="sr-only">, blocked</span>
        </>
      ) : null}
      {task.priority === "high" ? (
        <>
          <PriorityIcon priority="high" className="size-3.5" />
          <span className="sr-only">, high priority</span>
        </>
      ) : null}
      {menu}
    </div>
  );
}

/** Clicks on a chip's menu must not start a drag. */
function stop(event: ReactPointerEvent) {
  event.stopPropagation();
}

/**
 * A task's actions on the calendar: open it, copy its link, and --- where its
 * workspace allows --- every move a drag can make, by name.
 */
function ChipMenu({
  task,
  placement,
  today,
  onReschedule,
}: {
  task: Task;
  placement: Placement;
  today: string;
  onReschedule: (task: Task, dueDate: string | null) => void;
}) {
  const due = task.due_date;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          onPointerDown={stop}
          aria-label={`Actions for ${task.title}`}
          className={cn(
            // Laid over the end of the chip rather than beside it, so a narrow day
            // spends its width on the title; it appears on hover and on focus.
            "absolute inset-y-0 right-0.5 my-auto inline-flex size-5 items-center justify-center rounded bg-card text-muted-foreground shadow-xs ring-1 ring-border hover:text-foreground",
            "opacity-0 group-hover/chip:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100",
            // Touch screens have no hover to reveal it.
            "[@media(hover:none)]:opacity-100",
          )}
        >
          <MoreHorizontal aria-hidden="true" className="size-3.5" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem asChild>
          <Link href={placement.href}>
            <ExternalLink aria-hidden="true" />
            Open
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void copyTaskLink(placement.href)}>
          <Link2 aria-hidden="true" />
          Copy link
        </DropdownMenuItem>
        {placement.canEdit ? (
          <>
            <DropdownMenuSeparator />
            {due ? (
              <>
                <DropdownMenuItem onSelect={() => onReschedule(task, addDays(due, -1))}>
                  <ArrowLeft aria-hidden="true" />
                  Move to {shortDay(addDays(due, -1))}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => onReschedule(task, addDays(due, 1))}>
                  <ArrowRight aria-hidden="true" />
                  Move to {shortDay(addDays(due, 1))}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => onReschedule(task, addDays(due, 7))}>
                  <CalendarClock aria-hidden="true" />
                  Move a week later
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => onReschedule(task, null)}>
                  <CalendarX aria-hidden="true" />
                  Remove due date
                </DropdownMenuItem>
              </>
            ) : (
              <>
                <DropdownMenuItem onSelect={() => onReschedule(task, today)}>
                  <CalendarClock aria-hidden="true" />
                  Due today
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => onReschedule(task, addDays(today, 1))}>
                  <CalendarClock aria-hidden="true" />
                  Due tomorrow
                </DropdownMenuItem>
              </>
            )}
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
