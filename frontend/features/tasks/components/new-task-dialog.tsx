"use client";

import { useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { TaskForm } from "@/features/tasks/components/task-form";
import type { Task, TaskStatus } from "@/types/task";

/**
 * The full task form in a dialog. Opened from the toolbar's "New task", from a
 * board column's "+", or from quick add's "More options" (keeping what was typed).
 */
export function NewTaskDialog({
  workspaceId,
  shared,
  basePath,
  trigger,
  defaultStatus,
  initialTitle,
  onCreated,
}: {
  workspaceId: string;
  shared: boolean;
  basePath: string;
  trigger: ReactNode;
  defaultStatus?: TaskStatus;
  initialTitle?: string;
  onCreated?: (task: Task) => void;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [generation, setGeneration] = useState(0);

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
        title="New task"
        description={
          shared ? "Everyone in this company can see and edit it." : "Private: only you can see it."
        }
        className="max-w-xl"
      >
        <TaskForm
          key={generation}
          workspaceId={workspaceId}
          defaultStatus={defaultStatus}
          initialTitle={initialTitle}
          onCancel={() => setOpen(false)}
          onCreated={(task) => {
            setOpen(false);
            onCreated?.(task);
            toast("Task created", {
              description: task.title,
              action: { label: "Open", onClick: () => router.push(`${basePath}/${task.id}`) },
            });
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
