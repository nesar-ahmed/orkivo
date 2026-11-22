import { share } from "@/features/insights/insight-utils";
import type { TaskCounts } from "@/types/insights";

/**
 * One row of a workload chart: who, the bar, the numbers. Three columns from
 * `sm` up; on a phone the bar takes its own line under the other two, so it
 * never shrinks to nothing next to "4 open · 3 overdue".
 */
export const LOAD_ROW =
  "-mx-2 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 rounded-md px-2 py-2 hover:bg-muted sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)_auto]";

/**
 * Someone's open work as a bar: in progress, then still to do, scaled against the
 * busiest row so bars compare across people. Decorative: the numbers beside it
 * are the content.
 */
export function LoadBar({ counts, busiest }: { counts: TaskCounts; busiest: number }) {
  return (
    <span
      aria-hidden="true"
      className="order-last col-span-2 flex h-2 overflow-hidden rounded-full bg-muted sm:order-none sm:col-span-1"
    >
      <span
        className="h-full bg-status-progress"
        style={{ width: share(counts.in_progress, busiest) }}
      />
      <span className="h-full bg-status-todo/70" style={{ width: share(counts.todo, busiest) }} />
    </span>
  );
}

/** Open work, then what is overdue in red --- named in words as well as color. */
export function LoadNumbers({ counts }: { counts: TaskCounts }) {
  return (
    <span className="flex items-center justify-end gap-2 text-xs whitespace-nowrap tabular-nums">
      <span className="font-medium text-card-foreground">{counts.open} open</span>
      {counts.overdue > 0 ? (
        <span className="rounded-md bg-danger/10 px-1.5 py-0.5 font-medium text-danger">
          {counts.overdue} overdue
        </span>
      ) : null}
    </span>
  );
}

/** The legend both workload charts share. */
export function LoadLegend() {
  return (
    <p className="flex items-center gap-3 text-xs text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span aria-hidden="true" className="size-2 rounded-full bg-status-progress" />
        In progress
      </span>
      <span className="flex items-center gap-1.5">
        <span aria-hidden="true" className="size-2 rounded-full bg-status-todo/70" />
        To do
      </span>
    </p>
  );
}
