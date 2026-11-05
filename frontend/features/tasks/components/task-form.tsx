"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { createTask } from "@/features/tasks/api/task-mutations";
import {
  MAX_DUE_DATE,
  MIN_DUE_DATE,
  PRIORITY_LABELS,
  STATUS_LABELS,
  STATUS_ORDER,
} from "@/features/tasks/task-utils";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { Task, TaskPriority, TaskStatus } from "@/types/task";

const PRIORITIES: TaskPriority[] = ["low", "medium", "high"];

/**
 * The full create-task form, with every field. Validation feedback comes from
 * the backend contract and lands next to the field it is about.
 *
 * The task is created in `workspaceId`: in a company every member sees it at
 * once; in the private workspace nobody but its owner ever does.
 */
export function TaskForm({
  workspaceId,
  defaultStatus = "todo",
  initialTitle = "",
  onCreated,
  onCancel,
}: {
  workspaceId: string;
  defaultStatus?: TaskStatus;
  initialTitle?: string;
  onCreated?: (task: Task) => void;
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // This form is often rendered in a dialog portal. React events bubble through
    // the React tree, not the DOM, so without this an enclosing form (quick add)
    // would submit too and create the task twice.
    event.stopPropagation();
    const data = new FormData(event.currentTarget);

    startTransition(async () => {
      try {
        const task = await createTask(workspaceId, {
          title: String(data.get("title") ?? ""),
          description: String(data.get("description") ?? "") || null,
          status: String(data.get("status") ?? defaultStatus) as TaskStatus,
          priority: String(data.get("priority") ?? "medium") as TaskPriority,
          due_date: String(data.get("due_date") ?? "") || null,
        });
        setFieldErrors({});
        setGeneralError(null);
        onCreated?.(task);
        router.refresh();
      } catch (error) {
        const feedback = feedbackFromError(error);
        setFieldErrors(feedback.fieldErrors);
        setGeneralError(feedback.generalError);
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Create a new task" className="flex flex-col gap-4">
      <Field id="task-title" label="Title" required error={fieldErrors.title}>
        <Input
          id="task-title"
          name="title"
          required
          autoFocus
          maxLength={200}
          defaultValue={initialTitle}
          placeholder="e.g. Draft the release notes"
          aria-invalid={Boolean(fieldErrors.title)}
          disabled={isPending}
        />
      </Field>

      <Field id="task-description" label="Description" error={fieldErrors.description}>
        <Textarea
          id="task-description"
          name="description"
          rows={4}
          maxLength={5000}
          placeholder="Add details, links or acceptance criteria…"
          aria-invalid={Boolean(fieldErrors.description)}
          disabled={isPending}
        />
      </Field>

      <div className="grid gap-3 sm:grid-cols-3">
        <Field id="task-status" label="Status">
          <Select id="task-status" name="status" defaultValue={defaultStatus} disabled={isPending}>
            {STATUS_ORDER.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </Select>
        </Field>
        <Field id="task-priority" label="Priority">
          <Select id="task-priority" name="priority" defaultValue="medium" disabled={isPending}>
            {PRIORITIES.map((priority) => (
              <option key={priority} value={priority}>
                {PRIORITY_LABELS[priority]}
              </option>
            ))}
          </Select>
        </Field>
        <Field id="task-due" label="Due date" error={fieldErrors.due_date}>
          <Input
            id="task-due"
            name="due_date"
            type="date"
            min={MIN_DUE_DATE}
            max={MAX_DUE_DATE}
            aria-invalid={Boolean(fieldErrors.due_date)}
            disabled={isPending}
          />
        </Field>
      </div>

      {generalError ? (
        <p role="alert" className="rounded-md border border-danger/30 bg-danger/10 p-2.5 text-sm text-danger">
          {generalError}
        </p>
      ) : null}

      <div className="flex justify-end gap-2">
        {onCancel ? (
          <Button variant="secondary" size="sm" onClick={onCancel} disabled={isPending}>
            Cancel
          </Button>
        ) : null}
        <Button type="submit" size="sm" disabled={isPending}>
          {isPending ? "Adding…" : "Add task"}
        </Button>
      </div>
    </form>
  );
}

function Field({
  id,
  label,
  required,
  error,
  children,
}: {
  id: string;
  label: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-xs font-medium text-muted-foreground">
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {children}
      {error ? (
        <p role="alert" className="mt-1 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
