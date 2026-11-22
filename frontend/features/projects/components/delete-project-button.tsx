"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { deleteProject, isProjectConflict } from "@/features/projects/api/project-mutations";
import { ApiError } from "@/lib/api/client";
import type { ProjectSummary } from "@/types/project";

/**
 * Delete a project --- owners and admins only, which the page decides from the
 * workspace's `manage` capability and the API re-checks.
 *
 * It asks first, and says plainly that no task is lost: the tasks stay in the
 * workspace without a project. Deleting cannot be undone, which is why this asks
 * rather than offering Undo like a task delete.
 */
export function DeleteProjectButton({ project }: { project: ProjectSummary }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [isPending, startTransition] = useTransition();

  const tasks = project.task_count === 1 ? "task stays" : "tasks stay";
  const taskNote =
    project.task_count === 0
      ? "It holds no tasks."
      : `Its ${project.task_count} ${tasks} in the workspace, without a project.`;

  function handleConfirm() {
    startTransition(async () => {
      try {
        await deleteProject(project.id, project.version);
        toast("Project deleted", { description: project.name });
        router.refresh();
      } catch (error) {
        if (isProjectConflict(error)) {
          toast.error("Someone else changed this project a moment ago", {
            description: "Showing their version now. Delete again if you still want to.",
          });
        } else {
          toast.error("The project could not be deleted.", {
            description: error instanceof ApiError ? error.message : undefined,
          });
        }
        router.refresh();
      }
    });
  }

  return (
    <>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={`Delete ${project.name}`}
        onClick={() => setConfirming(true)}
        disabled={isPending}
      >
        <Trash2 aria-hidden="true" />
      </Button>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`Delete ${project.name}?`}
        description={`${taskNote} This cannot be undone.`}
        confirmLabel="Delete project"
        onConfirm={handleConfirm}
      />
    </>
  );
}
