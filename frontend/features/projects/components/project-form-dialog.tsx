"use client";

import { useState, useTransition, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  createProject,
  isProjectConflict,
  isProjectNameInUse,
  updateProject,
} from "@/features/projects/api/project-mutations";
import {
  PROJECT_DESCRIPTION_MAX_LENGTH,
  PROJECT_NAME_MAX_LENGTH,
} from "@/features/projects/project-utils";
import { ApiError } from "@/lib/api/client";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { Project, ProjectUpdateInput } from "@/types/project";

/**
 * Create a project, or rename and describe an existing one, in a dialog.
 *
 * Editing sends only what changed, with the version the page loaded: if a
 * colleague saved in between, the API refuses and the dialog says so instead of
 * overwriting them. A name another project already uses --- in any letter case ---
 * is shown on the name field, since that is the one thing to fix.
 */
export function ProjectFormDialog({
  workspaceId,
  project,
  trigger,
  shared,
}: {
  workspaceId: string;
  /** The project to edit; omit to create a new one. */
  project?: Project;
  trigger: ReactNode;
  shared: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [generation, setGeneration] = useState(0);
  const editing = project !== undefined;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        // A fresh form every time it opens.
        if (next) setGeneration((value) => value + 1);
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent
        title={editing ? "Edit project" : "New project"}
        description={
          shared
            ? "Everyone in this company can see it and file tasks under it."
            : "Private: only you can see it."
        }
        className="max-w-lg"
      >
        <ProjectForm
          key={generation}
          workspaceId={workspaceId}
          project={project}
          onDone={() => setOpen(false)}
        />
      </DialogContent>
    </Dialog>
  );
}

function ProjectForm({
  workspaceId,
  project,
  onDone,
}: {
  workspaceId: string;
  project?: Project;
  onDone: () => void;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Rendered in a dialog portal: keep the submit from reaching any form behind it.
    event.stopPropagation();
    const data = new FormData(event.currentTarget);
    const name = String(data.get("name") ?? "").trim();
    const description = String(data.get("description") ?? "").trim() || null;

    startTransition(async () => {
      try {
        if (project) {
          const changes: ProjectUpdateInput = {};
          if (name !== project.name) changes.name = name;
          if (description !== project.description) changes.description = description;
          if (Object.keys(changes).length > 0) {
            await updateProject(project.id, { ...changes, version: project.version });
            toast("Project saved", { description: name });
          }
        } else {
          await createProject(workspaceId, { name, description });
          toast("Project created", { description: name });
        }
        onDone();
        router.refresh();
      } catch (error) {
        if (isProjectNameInUse(error) && error instanceof ApiError) {
          setFieldErrors({ name: error.message });
          setGeneralError(null);
          return;
        }
        if (isProjectConflict(error)) {
          setFieldErrors({});
          setGeneralError(
            "Someone else changed this project a moment ago. Close this dialog to see their version.",
          );
          router.refresh();
          return;
        }
        const feedback = feedbackFromError(error, "The project could not be saved.");
        setFieldErrors(feedback.fieldErrors);
        setGeneralError(feedback.generalError);
      }
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      aria-label={project ? `Edit ${project.name}` : "Create a new project"}
      className="flex flex-col gap-4"
    >
      <div>
        <label htmlFor="project-name" className="mb-1.5 block text-xs font-medium text-muted-foreground">
          Name <span aria-hidden="true">*</span>
        </label>
        <Input
          id="project-name"
          name="name"
          required
          autoFocus
          maxLength={PROJECT_NAME_MAX_LENGTH}
          defaultValue={project?.name}
          placeholder="e.g. Website relaunch"
          aria-invalid={Boolean(fieldErrors.name)}
          aria-describedby={fieldErrors.name ? "project-name-error" : undefined}
          disabled={isPending}
        />
        {fieldErrors.name ? (
          <p id="project-name-error" role="alert" className="mt-1 text-xs text-danger">
            {fieldErrors.name}
          </p>
        ) : null}
      </div>

      <div>
        <label
          htmlFor="project-description"
          className="mb-1.5 block text-xs font-medium text-muted-foreground"
        >
          Description
        </label>
        <Textarea
          id="project-description"
          name="description"
          rows={3}
          maxLength={PROJECT_DESCRIPTION_MAX_LENGTH}
          defaultValue={project?.description ?? ""}
          placeholder="What this project is for, and when it is done."
          aria-invalid={Boolean(fieldErrors.description)}
          disabled={isPending}
        />
        {fieldErrors.description ? (
          <p role="alert" className="mt-1 text-xs text-danger">
            {fieldErrors.description}
          </p>
        ) : null}
      </div>

      {generalError ? (
        <p role="alert" className="rounded-md border border-danger/30 bg-danger/10 p-2.5 text-sm text-danger">
          {generalError}
        </p>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onDone} disabled={isPending}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={isPending}>
          {isPending ? "Saving…" : project ? "Save project" : "Create project"}
        </Button>
      </div>
    </form>
  );
}
