"use client";

import Link from "next/link";
import {
  ArrowRight,
  ChevronRight,
  ExternalLink,
  FolderInput,
  FolderKanban,
  FolderX,
  Link2,
  MoreHorizontal,
  Tag,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LabelDot } from "@/features/labels/components/label-chip";
import { MAX_LABELS_PER_TASK } from "@/features/labels/label-utils";
import { STATUS_LABELS, STATUS_ORDER } from "@/features/tasks/task-utils";
import type { Task, TaskLabel, TaskProject, TaskStatus } from "@/types/task";

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
 * The "⋯" menu on a task: open, copy its link, move it to another status or
 * project (the board's non-drag alternatives), add or remove a label, and delete
 * (with Undo).
 *
 * Each label toggle is one save and closes the menu, so two toggles can never race
 * each other with the same version; picking several at once is the task page's job.
 */
export function TaskRowMenu({
  task,
  href,
  onDelete,
  onMove,
  projects = [],
  onMoveToProject,
  labels = [],
  onRelabel,
}: {
  task: Task;
  href: string;
  onDelete?: () => void;
  onMove?: (status: TaskStatus) => void;
  /** The workspace's projects, offered by "Move to project". */
  projects?: readonly TaskProject[];
  onMoveToProject?: (project: TaskProject | null) => void;
  /** The workspace's labels, offered by "Labels". */
  labels?: readonly TaskLabel[];
  onRelabel?: (labels: TaskLabel[]) => void;
}) {
  const otherProjects = projects.filter((project) => project.id !== task.project?.id);
  const canMoveToProject = onMoveToProject && (otherProjects.length > 0 || task.project);
  // The task's own labels too, in case one was created after this page loaded.
  const knownLabels = [
    ...labels,
    ...task.labels.filter((label) => !labels.some((known) => known.id === label.id)),
  ];
  const carried = new Set(task.labels.map((label) => label.id));
  const full = task.labels.length >= MAX_LABELS_PER_TASK;
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
        {canMoveToProject ? (
          <>
            {onMove ? null : <DropdownMenuSeparator />}
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>
                <FolderInput aria-hidden="true" />
                Move to project
                <ChevronRight aria-hidden="true" className="ml-auto" />
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="max-h-72 w-52 overflow-y-auto">
                {otherProjects.map((project) => (
                  <DropdownMenuItem key={project.id} onSelect={() => onMoveToProject(project)}>
                    <FolderKanban aria-hidden="true" />
                    <span className="truncate">{project.name}</span>
                  </DropdownMenuItem>
                ))}
                {task.project ? (
                  <>
                    {otherProjects.length > 0 ? <DropdownMenuSeparator /> : null}
                    <DropdownMenuItem onSelect={() => onMoveToProject(null)}>
                      <FolderX aria-hidden="true" />
                      Remove from {task.project.name}
                    </DropdownMenuItem>
                  </>
                ) : null}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          </>
        ) : null}
        {onRelabel && knownLabels.length > 0 ? (
          <>
            {onMove || canMoveToProject ? null : <DropdownMenuSeparator />}
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>
                <Tag aria-hidden="true" />
                Labels
                <ChevronRight aria-hidden="true" className="ml-auto" />
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="max-h-72 w-52 overflow-y-auto">
                {knownLabels.map((label) => (
                  <DropdownMenuCheckboxItem
                    key={label.id}
                    checked={carried.has(label.id)}
                    disabled={full && !carried.has(label.id)}
                    onCheckedChange={(on) =>
                      onRelabel(
                        on === true
                          ? [...task.labels, label]
                          : task.labels.filter((current) => current.id !== label.id),
                      )
                    }
                  >
                    <LabelDot color={label.color} />
                    <span className="truncate">{label.name}</span>
                  </DropdownMenuCheckboxItem>
                ))}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
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
