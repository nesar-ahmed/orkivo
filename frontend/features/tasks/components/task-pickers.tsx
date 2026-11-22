"use client";

import { type ReactNode } from "react";
import { ChevronDown, FolderKanban, FolderX, Tag } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LabelChip, LabelDot } from "@/features/labels/components/label-chip";
import { MAX_LABELS_PER_TASK } from "@/features/labels/label-utils";
import { PriorityIcon, StatusIcon } from "@/features/tasks/components/task-icons";
import { UnassignedAvatar } from "@/features/tasks/components/task-meta";
import {
  PRIORITY_LABELS,
  STATUS_LABELS,
  STATUS_ORDER,
  assigneeName,
} from "@/features/tasks/task-utils";
import { cn } from "@/lib/utils/cn";
import type { TaskLabel, TaskPerson, TaskPriority, TaskProject, TaskStatus } from "@/types/task";

const PRIORITY_ORDER: TaskPriority[] = ["high", "medium", "low"];

/**
 * Status, priority, assignee and project as menus of radio items: the current value is
 * announced and checked, arrow keys move, Enter picks. Two looks --- a compact
 * icon button for rows and cards, and a labelled field for the task page. Labels
 * are a menu of checkboxes instead, since a task carries several.
 */

interface PickerProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  /** "icon": just the icon (rows, cards). "field": icon, label and chevron. */
  look?: "icon" | "field";
  disabled?: boolean;
  /** Names the task in the accessible label of an icon trigger. */
  taskTitle?: string;
  id?: string;
}

function triggerClasses(look: "icon" | "field") {
  return look === "icon"
    ? "inline-flex size-7 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-muted data-[state=open]:bg-muted"
    : cn(
        "flex h-9 w-full items-center gap-2 rounded-md border border-border bg-card px-3 text-sm shadow-xs",
        "transition-colors hover:border-border-strong data-[state=open]:border-primary",
      );
}

function Picker<T extends string>({
  value,
  onChange,
  look = "icon",
  disabled,
  label,
  options,
  labels,
  icon,
  accessibleName,
  id,
  contentClassName,
}: PickerProps<T> & {
  label: string;
  options: readonly T[];
  labels: Record<T, string>;
  icon: (value: T) => ReactNode;
  accessibleName: string;
  /** For menus that can grow long, such as a company's people. */
  contentClassName?: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        id={id}
        disabled={disabled}
        aria-label={accessibleName}
        className={triggerClasses(look)}
      >
        {icon(value)}
        {look === "field" ? (
          <>
            <span className="min-w-0 flex-1 truncate text-left">{labels[value]}</span>
            <ChevronDown aria-hidden="true" className="size-4 text-muted-foreground" />
          </>
        ) : null}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className={cn("w-44", contentClassName)}>
        <DropdownMenuLabel>{label}</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={value} onValueChange={(next) => onChange(next as T)}>
          {options.map((option) => (
            <DropdownMenuRadioItem key={option} value={option}>
              {icon(option)}
              {labels[option]}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function StatusPicker(props: PickerProps<TaskStatus>) {
  const name = props.taskTitle
    ? `Status of ${props.taskTitle}: ${STATUS_LABELS[props.value]}`
    : `Status: ${STATUS_LABELS[props.value]}`;
  return (
    <Picker
      {...props}
      label="Status"
      options={STATUS_ORDER}
      labels={STATUS_LABELS}
      icon={(value) => <StatusIcon status={value} />}
      accessibleName={name}
    />
  );
}

export function PriorityPicker(props: PickerProps<TaskPriority>) {
  const name = props.taskTitle
    ? `Priority of ${props.taskTitle}: ${PRIORITY_LABELS[props.value]}`
    : `Priority: ${PRIORITY_LABELS[props.value]}`;
  return (
    <Picker
      {...props}
      label="Priority"
      options={PRIORITY_ORDER}
      labels={PRIORITY_LABELS}
      icon={(value) => <PriorityIcon priority={value} />}
      accessibleName={name}
    />
  );
}

/** The radio value standing for "nobody"; never a member id. */
const UNASSIGNED = "none";

/**
 * Who holds the task. `value` is a member id, or `""` for nobody --- the same
 * "empty string means no value" convention as the task page's other fields.
 *
 * `people` is what the picker can offer. Pass the current assignee along with
 * the members, so a task held by someone outside the loaded page of members
 * still shows their name instead of an id.
 */
export function AssigneePicker({
  value,
  onChange,
  people,
  viewerId,
  look,
  disabled,
  taskTitle,
  id,
}: Omit<PickerProps<string>, "onChange"> & {
  onChange: (value: string) => void;
  people: readonly TaskPerson[];
  viewerId: string | null;
}) {
  const byId = new Map(people.map((person) => [person.id, person]));
  const options = [UNASSIGNED, ...byId.keys()];
  const labels: Record<string, string> = { [UNASSIGNED]: "Unassigned" };
  for (const person of byId.values()) labels[person.id] = assigneeName(person, viewerId);
  const current = value || UNASSIGNED;
  if (!(current in labels)) labels[current] = "A former member";

  const name = `${taskTitle ? `Assignee of ${taskTitle}` : "Assignee"}: ${labels[current]}`;
  return (
    <Picker<string>
      value={current}
      onChange={(next) => onChange(next === UNASSIGNED ? "" : next)}
      look={look}
      disabled={disabled}
      id={id}
      label="Assignee"
      options={options}
      labels={labels}
      icon={(option) => {
        const person = byId.get(option);
        return person ? (
          <Avatar name={person.display_name} seed={person.id} size="xs" />
        ) : (
          <UnassignedAvatar size="xs" />
        );
      }}
      accessibleName={name}
      contentClassName="max-h-72 w-56 overflow-y-auto"
    />
  );
}

/** The radio value standing for "no project"; never a project id. */
const NO_PROJECT = "none";

/**
 * The project a task is filed under. `value` is a project id, or `""` for none.
 *
 * `projects` is what the picker can offer. Pass the task's current project along
 * with the workspace's, so one outside the loaded page still shows by name.
 */
export function ProjectPicker({
  value,
  onChange,
  projects,
  look,
  disabled,
  taskTitle,
  id,
}: Omit<PickerProps<string>, "onChange"> & {
  onChange: (value: string) => void;
  projects: readonly TaskProject[];
}) {
  const byId = new Map(projects.map((project) => [project.id, project]));
  const options = [NO_PROJECT, ...byId.keys()];
  const labels: Record<string, string> = { [NO_PROJECT]: "No project" };
  for (const project of byId.values()) labels[project.id] = project.name;
  const current = value || NO_PROJECT;
  if (!(current in labels)) labels[current] = "A deleted project";

  const name = `${taskTitle ? `Project of ${taskTitle}` : "Project"}: ${labels[current]}`;
  return (
    <Picker<string>
      value={current}
      onChange={(next) => onChange(next === NO_PROJECT ? "" : next)}
      look={look}
      disabled={disabled}
      id={id}
      label="Project"
      options={options}
      labels={labels}
      icon={(option) =>
        option === NO_PROJECT ? (
          <FolderX aria-hidden="true" className="size-4 text-muted-foreground" />
        ) : (
          <FolderKanban aria-hidden="true" className="size-4 text-muted-foreground" />
        )
      }
      accessibleName={name}
      contentClassName="max-h-72 w-56 overflow-y-auto"
    />
  );
}

/** How many chips the field shows before the rest become "+N". */
const LABELS_IN_FIELD = 6;

/**
 * The labels a task carries, as a menu of checkboxes that stays open so several
 * can be picked in one go. `value` is the chosen label ids, in any order.
 *
 * `labels` is what the picker can offer, alphabetically. Pass the task's current
 * labels along with the workspace's, so one created since the page loaded still
 * shows by name. Once a task is full, the unchosen labels are disabled and the
 * menu says why, rather than letting the API refuse the save.
 */
export function LabelPicker({
  value,
  onChange,
  labels,
  disabled,
  taskTitle,
  id,
}: {
  value: readonly string[];
  onChange: (value: string[]) => void;
  labels: readonly TaskLabel[];
  disabled?: boolean;
  taskTitle?: string;
  id?: string;
}) {
  const chosen = new Set(value);
  const selected = labels.filter((label) => chosen.has(label.id));
  const full = value.length >= MAX_LABELS_PER_TASK;
  const summary =
    selected.length === 0 ? "No labels" : selected.map((label) => label.name).join(", ");
  const name = `${taskTitle ? `Labels of ${taskTitle}` : "Labels"}: ${summary}`;

  function toggle(labelId: string, on: boolean) {
    onChange(on ? [...value, labelId] : value.filter((current) => current !== labelId));
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        id={id}
        disabled={disabled}
        aria-label={name}
        className={cn(triggerClasses("field"), "h-auto min-h-9 py-1.5")}
      >
        {selected.length > 0 ? (
          // Plain chips: the trigger is a button, so nothing inside it may be focusable.
          <span className="flex min-w-0 flex-1 flex-wrap items-center gap-1">
            {selected.slice(0, LABELS_IN_FIELD).map((label) => (
              <LabelChip key={label.id} label={label} />
            ))}
            {selected.length > LABELS_IN_FIELD ? (
              <span className="text-xs text-muted-foreground">
                +{selected.length - LABELS_IN_FIELD}
              </span>
            ) : null}
          </span>
        ) : (
          <span className="flex min-w-0 flex-1 items-center gap-2 text-muted-foreground">
            <Tag aria-hidden="true" className="size-4" />
            No labels
          </span>
        )}
        <ChevronDown aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-72 w-56 overflow-y-auto">
        <DropdownMenuLabel>Labels</DropdownMenuLabel>
        {labels.length === 0 ? (
          <p className="px-2 pb-2 text-xs text-muted-foreground">
            This workspace has no labels yet. Create them on its Labels page.
          </p>
        ) : (
          labels.map((label) => (
            <DropdownMenuCheckboxItem
              key={label.id}
              checked={chosen.has(label.id)}
              disabled={full && !chosen.has(label.id)}
              onCheckedChange={(on) => toggle(label.id, on === true)}
              // Keep the menu open: labels are usually picked several at a time.
              onSelect={(event) => event.preventDefault()}
            >
              <LabelDot color={label.color} />
              <span className="truncate">{label.name}</span>
            </DropdownMenuCheckboxItem>
          ))
        )}
        {full ? (
          <p className="px-2 pt-1 pb-2 text-xs text-muted-foreground">
            A task can carry up to {MAX_LABELS_PER_TASK} labels.
          </p>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
