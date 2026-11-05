"use client";

import Link from "next/link";
import { ArrowRight, ExternalLink, Link2, MoreHorizontal, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { STATUS_LABELS, STATUS_ORDER } from "@/features/tasks/task-utils";
import type { Task, TaskStatus } from "@/types/task";

/** Copy a task's address; only members of its workspace can open it. */
export async function copyTaskLink(href: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(new URL(href, window.location.origin).toString());
    toast("Link copied", { description: "Only members of this workspace can open it." });
  } catch {
    toast.error("Could not copy the link", {
      description: "Open the task and copy the address from the browser bar.",
    });
  }
}

/**
 * The "⋯" menu on a task: open, copy its link, move it to another status (the
 * board's non-drag alternative), and delete (with Undo).
 */
export function TaskRowMenu({
  task,
  href,
  onDelete,
  onMove,
}: {
  task: Task;
  href: string;
  onDelete?: () => void;
  onMove?: (status: TaskStatus) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={`Actions for ${task.title}`}
          className="data-[state=open]:bg-muted"
        >
          <MoreHorizontal aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem asChild>
          <Link href={href}>
            <ExternalLink aria-hidden="true" />
            Open
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void copyTaskLink(href)}>
          <Link2 aria-hidden="true" />
          Copy link
        </DropdownMenuItem>
        {onMove ? (
          <>
            <DropdownMenuSeparator />
            {STATUS_ORDER.filter((status) => status !== task.status).map((status) => (
              <DropdownMenuItem key={status} onSelect={() => onMove(status)}>
                <ArrowRight aria-hidden="true" />
                Move to {STATUS_LABELS[status]}
              </DropdownMenuItem>
            ))}
          </>
        ) : null}
        {onDelete ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onSelect={onDelete}>
              <Trash2 aria-hidden="true" />
              Delete
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
