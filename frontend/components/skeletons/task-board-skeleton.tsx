import { Skeleton } from "@/components/ui/skeleton";

/** The shape of a task list while it loads, so the page does not jump. */
export function TaskBoardSkeleton() {
  return (
    <div className="flex flex-col gap-4" role="status" aria-label="Loading tasks">
      <Skeleton className="h-6 w-24" />
      <div className="flex gap-2">
        <Skeleton className="h-8 w-36" />
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-8 w-24" />
      </div>
      <Skeleton className="h-11 w-full rounded-xl" />
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        {Array.from({ length: 6 }, (_, index) => (
          <div key={index} className="flex items-center gap-3 border-b border-border px-3 py-3 last:border-0">
            <Skeleton className="size-5 rounded-full" />
            <Skeleton className="h-4 flex-1" style={{ maxWidth: `${60 - index * 5}%` }} />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="size-6 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** A table's shape while it loads. */
export function TableSkeleton({ label, rows = 4 }: { label: string; rows?: number }) {
  return (
    <div className="flex flex-col gap-3" role="status" aria-label={label}>
      <Skeleton className="h-5 w-28" />
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        {Array.from({ length: rows }, (_, index) => (
          <div key={index} className="flex items-center gap-3 border-b border-border px-4 py-3 last:border-0">
            <Skeleton className="size-8 rounded-full" />
            <Skeleton className="h-4 w-48" />
            <Skeleton className="ml-auto h-4 w-20" />
          </div>
        ))}
      </div>
    </div>
  );
}
