"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import { createTask } from "@/features/tasks/api/task-mutations";
import { PRIORITY_LABELS } from "@/features/tasks/task-utils";
import type { TaskPriority } from "@/types/task";

const PRIORITIES = Object.keys(PRIORITY_LABELS) as TaskPriority[];

/** Create-task form: validation feedback comes from the backend contract. */
export function TaskForm() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    const form = event.currentTarget;
    event.preventDefault();
    const data = new FormData(form);

    startTransition(async () => {
      try {
        await createTask({
          title: String(data.get("title") ?? ""),
          description: String(data.get("description") ?? "") || null,
          priority: (String(data.get("priority") ?? "medium") as TaskPriority) || "medium",
          due_date: String(data.get("due_date") ?? "") || null,
        });
        form.reset();
        setFieldErrors({});
        setGeneralError(null);
        router.refresh();
      } catch (err) {
        if (err instanceof ApiError && err.code === "VALIDATION_ERROR") {
          const next: Record<string, string> = {};
          for (const detail of err.details) {
            if (detail.field) next[detail.field] = detail.message;
          }
          setFieldErrors(next);
          setGeneralError(
            Object.keys(next).length === 0 ? "Please check the form and try again." : null,
          );
        } else {
          setFieldErrors({});
          setGeneralError(
            err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
          );
        }
      }
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-border bg-card p-5 shadow-sm"
      aria-label="Create a new task"
    >
      <h2 className="text-sm font-semibold text-card-foreground">New task</h2>

      <div className="mt-4 flex flex-col gap-4">
        <div>
          <label htmlFor="task-title" className="mb-1 block text-xs font-medium text-foreground">
            Title <span aria-hidden="true">*</span>
          </label>
          <Input
            id="task-title"
            name="title"
            required
            maxLength={200}
            placeholder="e.g. Draft the release notes"
            aria-invalid={Boolean(fieldErrors.title)}
            disabled={isPending}
          />
          {fieldErrors.title ? (
            <p role="alert" className="mt-1 text-xs text-danger">
              {fieldErrors.title}
            </p>
          ) : null}
        </div>

        <div>
          <label
            htmlFor="task-description"
            className="mb-1 block text-xs font-medium text-foreground"
          >
            Description
          </label>
          <Textarea
            id="task-description"
            name="description"
            rows={3}
            maxLength={5000}
            placeholder="Optional details…"
            disabled={isPending}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label
              htmlFor="task-priority"
              className="mb-1 block text-xs font-medium text-foreground"
            >
              Priority
            </label>
            <Select id="task-priority" name="priority" defaultValue="medium" disabled={isPending}>
              {PRIORITIES.map((priority) => (
                <option key={priority} value={priority}>
                  {PRIORITY_LABELS[priority]}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label htmlFor="task-due" className="mb-1 block text-xs font-medium text-foreground">
              Due date
            </label>
            <Input id="task-due" name="due_date" type="date" disabled={isPending} />
          </div>
        </div>
      </div>

      {generalError ? (
        <p role="alert" className="mt-3 text-xs text-danger">
          {generalError}
        </p>
      ) : null}

      <Button type="submit" className="mt-5 w-full" disabled={isPending}>
        {isPending ? "Adding…" : "Add task"}
      </Button>
    </form>
  );
}
