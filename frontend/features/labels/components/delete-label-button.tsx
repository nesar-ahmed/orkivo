"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { deleteLabel, isLabelConflict } from "@/features/labels/api/label-mutations";
import { ApiError } from "@/lib/api/client";
import type { LabelSummary } from "@/types/label";

/**
 * Delete a label --- owners and admins only, which the page decides from the
 * workspace's `manage` capability and the API re-checks.
 *
 * It asks first, and says plainly what happens to the work: the label is taken
 * off its tasks, which stay where they are. Deleting cannot be undone, which is
 * why this asks rather than offering Undo like a task delete.
 */
export function DeleteLabelButton({ label }: { label: LabelSummary }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [isPending, startTransition] = useTransition();

  const taskNote =
    label.task_count === 0
      ? "No task carries it."
      : `It will be taken off ${label.task_count} ${
          label.task_count === 1 ? "task" : "tasks"
        }; the tasks themselves stay.`;

  function handleConfirm() {
    startTransition(async () => {
      try {
        await deleteLabel(label.id, label.version);
        toast("Label deleted", { description: label.name });
        router.refresh();
      } catch (error) {
        if (isLabelConflict(error)) {
          toast.error("Someone else changed this label a moment ago", {
            description: "Showing their version now. Delete again if you still want to.",
          });
        } else {
          toast.error("The label could not be deleted.", {
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
        aria-label={`Delete ${label.name}`}
        onClick={() => setConfirming(true)}
        disabled={isPending}
      >
        <Trash2 aria-hidden="true" />
      </Button>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`Delete ${label.name}?`}
        description={`${taskNote} This cannot be undone.`}
        confirmLabel="Delete label"
        onConfirm={handleConfirm}
      />
    </>
  );
}
