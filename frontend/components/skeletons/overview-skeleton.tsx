import { Skeleton } from "@/components/ui/skeleton";

/** A dashboard's shape while it loads: the number tiles, then the cards. */
export function OverviewSkeleton() {
  return (
    <div className="flex flex-col gap-5" role="status" aria-label="Loading the overview">
      <Skeleton className="h-6 w-64" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-24 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-72 rounded-xl lg:col-span-2" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
      <Skeleton className="h-48 rounded-xl" />
    </div>
  );
}
