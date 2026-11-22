import { Skeleton } from "@/components/ui/skeleton";

/** Shown while a company's automation rules load. */
export default function Loading() {
  return (
    <div className="flex flex-col gap-4" role="status" aria-label="Loading automations">
      <Skeleton className="h-6 w-40" />
      <Skeleton className="h-4 w-96 max-w-full" />
      {Array.from({ length: 3 }, (_, index) => (
        <Skeleton key={index} className="h-28 rounded-xl" />
      ))}
    </div>
  );
}
