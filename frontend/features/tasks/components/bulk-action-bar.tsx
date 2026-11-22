"use client";

import { useState, type ReactNode } from "react";
import {
  CalendarClock,
  CalendarX,
  ChevronDown,
  FolderKanban,
  FolderX,
  Tag,
  TagX,
  Trash2,
  X,
} from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { Button, buttonClasses } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { LabelDot } from "@/features/labels/components/label-chip";
import { PriorityIcon, StatusIcon } from "@/features/tasks/components/task-icons";
import { UnassignedAvatar } from "@/features/tasks/components/task-meta";
import { addDays } from "@/features/tasks/task-dates";
import {
  MAX_DUE_DATE,
  MIN_DUE_DATE,
  PRIORITY_LABELS,
  STATUS_LABELS,
  STATUS_ORDER,
  assigneeName,
  taskCan,
  type TaskChoices,
} from "@/features/tasks/task-utils";
import type { BulkEdit } from "@/features/tasks/use-task-actions";
import { useToday } from "@/features/tasks/use-today";
import { cn } from "@/lib/utils/cn";
import type { Task, TaskPriority } from "@/types/task";

const PRIORITY_ORDER: TaskPriority[] = ["high", "medium", "low"];

/**
 * What can be done to a list's selection: set the status, priority, assignee,
 * project or due date of every selected task, add or remove a label, or delete
 * them --- each one save with one Undo.
 *
 * Sticky at the bottom of the list while anything is selected, the way Linear,
 * GitHub and Gmail put bulk actions where the selection is. Each action applies
 * to the selected tasks the caller may change (each task's own `capabilities`);
 * when some of the selection is not theirs, the bar says how many, and those are
 * left alone rather than failing the whole save. Delete counts only the tasks
 * the caller may delete.
 */
export function BulkActionBar({
  selected,
  choices,
  onEdit,
  onDelete,
  onClear,
}: {
  selected: readonly Task[];
  choices: TaskChoices;
  onEdit: (tasks: readonly Task[], edit: BulkEdit) => void;
  onDelete: (tasks: readonly Task[]) => void;
  onClear: () => void;
}) {
  const editable = selected.filter((task) => taskCan(task, "edit"));
  const deletable = selected.filter((task) => taskCan(task, "delete"));
  const readOnly = selected.length - editable.length;
  const edit = (change: BulkEdit) => onEdit(editable, change);
  const canEdit = editable.length > 0;
  // Labels carried by any task that may change, so "Remove" only offers real ones.
  const carried = choices.labels.filter((label) =>
    editable.some((task) => task.labels.some((held) => held.id === label.id)),
  );

  return (
    <div
      role="toolbar"
      aria-label={`Actions for ${selected.length} selected ${selected.length === 1 ? "task" : "tasks"}`}
      className="sticky bottom-4 z-20 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-popover/95 p-2 pl-3 shadow-lg backdrop-blur animate-pop-in"
    >
      <p aria-live="polite" className="mr-1 text-sm font-medium text-popover-foreground">
        {selected.length} selected
        {readOnly > 0 ? (
          <span className="ml-1.5 text-xs font-normal text-muted-foreground">
            · {readOnly} you can&rsquo;t change
          </span>
        ) : null}
      </p>

      <BarMenu label="Status" disabled={!canEdit}>
        {STATUS_ORDER.map((status) => (
          <DropdownMenuItem key={status} onSelect={() => edit({ field: "status", value: status })}>
            <StatusIcon status={status} />
            {STATUS_LABELS[status]}
          </DropdownMenuItem>
        ))}
      </BarMenu>

      <BarMenu label="Priority" disabled={!canEdit}>
        {PRIORITY_ORDER.map((priority) => (
          <DropdownMenuItem
            key={priority}
            onSelect={() => edit({ field: "priority", value: priority })}
          >
            <PriorityIcon priority={priority} />
            {PRIORITY_LABELS[priority]}
          </DropdownMenuItem>
        ))}
      </BarMenu>

      <BarMenu label="Assignee" disabled={!canEdit} wide>
        <DropdownMenuItem onSelect={() => edit({ field: "assignee", value: null })}>
          <UnassignedAvatar size="xs" />
          Unassigned
        </DropdownMenuItem>
        {choices.assignees.members.length > 0 ? <DropdownMenuSeparator /> : null}
        {choices.assignees.members.map((person) => (
          <DropdownMenuItem
            key={person.id}
            onSelect={() => edit({ field: "assignee", value: person })}
          >
            <Avatar name={person.display_name} seed={person.id} size="xs" />
            <span className="truncate">{assigneeName(person, choices.assignees.viewerId)}</span>
          </DropdownMenuItem>
        ))}
      </BarMenu>

      <BarMenu label="Project" disabled={!canEdit} wide>
        <DropdownMenuItem onSelect={() => edit({ field: "project", value: null })}>
          <FolderX aria-hidden="true" />
          No project
        </DropdownMenuItem>
        {choices.projects.length > 0 ? <DropdownMenuSeparator /> : null}
        {choices.projects.map((project) => (
          <DropdownMenuItem key={project.id} onSelect={() => edit({ field: "project", value: project })}>
            <FolderKanban aria-hidden="true" />
            <span className="truncate">{project.name}</span>
          </DropdownMenuItem>
        ))}
      </BarMenu>

      <BarMenu label="Labels" disabled={!canEdit || choices.labels.length === 0}>
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <Tag aria-hidden="true" />
            Add a label
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="max-h-72 w-52 overflow-y-auto">
            {choices.labels.map((label) => (
              <DropdownMenuItem
                key={label.id}
                onSelect={() => edit({ field: "addLabel", value: label })}
              >
                <LabelDot color={label.color} />
                <span className="truncate">{label.name}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuSub>
          <DropdownMenuSubTrigger disabled={carried.length === 0}>
            <TagX aria-hidden="true" />
            Remove a label
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="max-h-72 w-52 overflow-y-auto">
            {carried.map((label) => (
              <DropdownMenuItem
                key={label.id}
                onSelect={() => edit({ field: "removeLabel", value: label })}
              >
                <LabelDot color={label.color} />
                <span className="truncate">{label.name}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>
      </BarMenu>

      <DueDateControl
        disabled={!canEdit}
        onPick={(value) => edit({ field: "due", value })}
      />

      <div className="ml-auto flex items-center gap-1">
        <Button
          variant="danger"
          size="sm"
          disabled={deletable.length === 0}
          onClick={() => onDelete(deletable)}
        >
          <Trash2 aria-hidden="true" />
          Delete{deletable.length > 0 && deletable.length < selected.length ? ` ${deletable.length}` : ""}
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label="Clear the selection" onClick={onClear}>
          <X aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}

/** One of the bar's menus: a labelled button that opens a list of choices. */
function BarMenu({
  label,
  disabled,
  wide = false,
  children,
}: {
  label: string;
  disabled: boolean;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={disabled}
        className={cn(buttonClasses("secondary", "sm"), "gap-1.5")}
      >
        {label}
        <ChevronDown aria-hidden="true" className="size-3.5 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        side="top"
        className={cn(wide ? "max-h-72 w-56 overflow-y-auto" : "w-44")}
      >
        <DropdownMenuLabel>Set {label.toLowerCase()}</DropdownMenuLabel>
        {children}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * The due date: the common choices in one click, or any day from a date field.
 * A popover rather than a menu, because a menu cannot hold a text field.
 */
function DueDateControl({
  disabled,
  onPick,
}: {
  disabled: boolean;
  onPick: (value: string | null) => void;
}) {
  const today = useToday();
  const [open, setOpen] = useState(false);
  const [day, setDay] = useState("");
  const pick = (value: string | null) => {
    setOpen(false);
    setDay("");
    onPick(value);
  };
  const quick: { label: string; value: string }[] = [
    { label: "Today", value: today },
    { label: "Tomorrow", value: addDays(today, 1) },
    { label: "In a week", value: addDays(today, 7) },
  ];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger disabled={disabled} className={cn(buttonClasses("secondary", "sm"), "gap-1.5")}>
        Due date
        <ChevronDown aria-hidden="true" className="size-3.5 text-muted-foreground" />
      </PopoverTrigger>
      <PopoverContent side="top" align="start" className="flex w-60 flex-col gap-2 p-2">
        <p className="px-1 text-xs font-medium text-muted-foreground">Set due date</p>
        <div className="flex flex-col">
          {quick.map((option) => (
            <button
              key={option.label}
              type="button"
              onClick={() => pick(option.value)}
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
            >
              <CalendarClock aria-hidden="true" className="size-4 text-muted-foreground" />
              {option.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => pick(null)}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
          >
            <CalendarX aria-hidden="true" className="size-4 text-muted-foreground" />
            No due date
          </button>
        </div>
        <form
          className="flex items-center gap-2 border-t border-border pt-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (day) pick(day);
          }}
        >
          <label htmlFor="bulk-due-date" className="sr-only">
            Another day
          </label>
          <input
            id="bulk-due-date"
            type="date"
            value={day}
            min={MIN_DUE_DATE}
            max={MAX_DUE_DATE}
            onChange={(event) => setDay(event.target.value)}
            className="h-8 min-w-0 flex-1 rounded-md border border-border bg-card px-2 text-sm focus-visible:border-primary focus-visible:outline-none"
          />
          <Button type="submit" size="sm" disabled={!day}>
            Set
          </Button>
        </form>
      </PopoverContent>
    </Popover>
  );
}
