"use client";

import { type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PriorityIcon, StatusIcon } from "@/features/tasks/components/task-icons";
import {
  PRIORITY_LABELS,
  STATUS_LABELS,
  STATUS_ORDER,
} from "@/features/tasks/task-utils";
import { cn } from "@/lib/utils/cn";
import type { TaskPriority, TaskStatus } from "@/types/task";

const PRIORITY_ORDER: TaskPriority[] = ["high", "medium", "low"];

/**
 * Status and priority as menus of radio items: the current value is announced
 * and checked, arrow keys move, Enter picks. Two looks --- a compact icon button
 * for rows and cards, and a labelled field for the task page.
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
}: PickerProps<T> & {
  label: string;
  options: readonly T[];
  labels: Record<T, string>;
  icon: (value: T) => ReactNode;
  accessibleName: string;
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
            <span className="flex-1 text-left">{labels[value]}</span>
            <ChevronDown aria-hidden="true" className="size-4 text-muted-foreground" />
          </>
        ) : null}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-44">
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
