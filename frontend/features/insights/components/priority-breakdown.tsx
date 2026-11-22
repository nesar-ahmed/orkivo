import Link from "next/link";
import { PriorityIcon } from "@/features/tasks/components/task-icons";
import { PRIORITY_LABELS } from "@/features/tasks/task-utils";
import { share } from "@/features/insights/insight-utils";
import { cn } from "@/lib/utils/cn";
import type { PriorityCounts } from "@/types/insights";
import type { TaskPriority } from "@/types/task";

const ORDER: readonly TaskPriority[] = ["high", "medium", "low"];

const BAR_COLORS: Record<TaskPriority, string> = {
  high: "bg-priority-high",
  medium: "bg-priority-medium",
  low: "bg-priority-low",
};

/**
 * Open work per priority, as bars scaled to the largest --- so "how much of what
 * is left is urgent?" reads at a glance, and each row opens that slice.
 */
export function PriorityBreakdown({
  counts,
  hrefFor,
}: {
  counts: PriorityCounts;
  hrefFor: (priority: TaskPriority) => string;
}) {
  const largest = Math.max(...ORDER.map((priority) => counts[priority]));
  return (
    <ul className="flex flex-col gap-1">
      {ORDER.map((priority) => (
        <li key={priority}>
          <Link
            href={hrefFor(priority)}
            className="-mx-2 grid grid-cols-[6.5rem_minmax(0,1fr)_2.5rem] items-center gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
          >
            <span className="flex items-center gap-2 text-card-foreground">
              <PriorityIcon priority={priority} />
              {PRIORITY_LABELS[priority]}
            </span>
            <span aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-muted">
              <span
                className={cn("block h-full rounded-full", BAR_COLORS[priority])}
                style={{ width: share(counts[priority], largest) }}
              />
            </span>
            <span className="text-right font-medium tabular-nums">
              {counts[priority]}
              <span className="sr-only"> open</span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
