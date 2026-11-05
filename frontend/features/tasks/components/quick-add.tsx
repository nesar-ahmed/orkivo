"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { createTask } from "@/features/tasks/api/task-mutations";
import { NewTaskDialog } from "@/features/tasks/components/new-task-dialog";
import { feedbackFromError } from "@/lib/api/form-feedback";

/**
 * Type a title, press Enter: the fastest way to capture a task. It sits at the
 * top of the list --- on a phone too --- and "More options" opens the full form
 * with what was already typed.
 */
export function QuickAdd({
  workspaceId,
  shared,
  basePath,
}: {
  workspaceId: string;
  shared: boolean;
  basePath: string;
}) {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = title.trim();
    if (!value) return;
    startTransition(async () => {
      try {
        const task = await createTask(workspaceId, { title: value });
        setTitle("");
        setError(null);
        toast("Task created", {
          description: task.title,
          action: { label: "Open", onClick: () => router.push(`${basePath}/${task.id}`) },
        });
        router.refresh();
      } catch (err) {
        const feedback = feedbackFromError(err);
        setError(feedback.fieldErrors.title ?? feedback.generalError);
      }
    });
  }

  return (
    <div>
      <div className="flex items-center gap-2 rounded-xl border border-dashed border-border-strong bg-card/70 py-1.5 pr-1.5 pl-3 transition-colors focus-within:border-primary focus-within:bg-card">
        <form onSubmit={handleSubmit} className="flex min-w-0 flex-1 items-center gap-2">
          <Plus aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
          <label htmlFor="quick-add-title" className="sr-only">
            New task title
          </label>
          <input
            id="quick-add-title"
            value={title}
            maxLength={200}
            onChange={(event) => setTitle(event.target.value)}
            placeholder={shared ? "Add a task for the team…" : "Add a private task…"}
            disabled={isPending}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "quick-add-error" : undefined}
            className="h-8 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
            <Kbd>Enter</Kbd> to add
          </span>
        </form>
        {/* Outside the quick-add form on purpose: the dialog's own form must not
            be nested in this one (see TaskForm). */}
        <NewTaskDialog
          workspaceId={workspaceId}
          shared={shared}
          basePath={basePath}
          initialTitle={title}
          onCreated={() => setTitle("")}
          trigger={
            <Button variant="ghost" size="xs">
              More options
            </Button>
          }
        />
      </div>
      {error ? (
        <p id="quick-add-error" role="alert" className="mt-1 px-1 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
