import Link from "next/link";
import { StatusIcon } from "@/features/tasks/components/task-icons";
import { STATUS_LABELS, STATUS_ORDER } from "@/features/tasks/task-utils";
import { percent, share } from "@/features/insights/insight-utils";
import { cn } from "@/lib/utils/cn";
import type { TaskCounts } from "@/types/insights";
import type { TaskStatus } from "@/types/task";

const SEGMENT_COLORS: Record<TaskStatus, string> = {
  todo: "bg-status-todo",
  in_progress: "bg-status-progress",
  done: "bg-status-done",
};

/**
 * Where the work stands: one bar split by status, and a legend that doubles as
 * the way into each status's list.
 *
 * A single stacked bar rather than a donut: lengths compare more accurately than
 * angles, it reads at any width, and the legend carries every number as text, so
 * the bar itself is decoration with a summary for assistive technology.
 */
export function StatusBreakdown({
  counts,
  hrefFor,
}: {
  counts: TaskCounts;
  hrefFor: (status: TaskStatus) => string;
}) {
  const byStatus: Record<TaskStatus, number> = {
    todo: counts.todo,
    in_progress: counts.in_progress,
    done: counts.done,
  };
  const summary = STATUS_ORDER.map((status) => `${byStatus[status]} ${STATUS_LABELS[status]}`).join(
    ", ",
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          <span className="text-2xl font-semibold tracking-tight text-card-foreground tabular-nums">
            {percent(counts.done, counts.total)}%
          </span>{" "}
          done
        </p>
        <p className="text-xs text-muted-foreground tabular-nums">
          {counts.done} of {counts.total}
        </p>
      </div>
      <div
        role="img"
        aria-label={counts.total > 0 ? `Tasks by status: ${summary}.` : "No tasks yet."}
        className="flex h-2.5 overflow-hidden rounded-full bg-muted"
      >
        {STATUS_ORDER.map((status) =>
          byStatus[status] > 0 ? (
            <span
              key={status}
              className={cn("h-full", SEGMENT_COLORS[status])}
              style={{ width: share(byStatus[status], counts.total) }}
            />
          ) : null,
        )}
      </div>
      <ul className="flex flex-col">
        {STATUS_ORDER.map((status) => (
          <li key={status}>
            <Link
              href={hrefFor(status)}
              className="-mx-2 flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
            >
              <StatusIcon status={status} />
              <span className="flex-1 text-card-foreground">{STATUS_LABELS[status]}</span>
              <span className="font-medium tabular-nums">{byStatus[status]}</span>
              <span className="w-10 text-right text-xs text-muted-foreground tabular-nums">
                {percent(byStatus[status], counts.total)}%
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
