import { TableSkeleton } from "@/components/skeletons/task-board-skeleton";

/** Shown while the feed loads. The company itself was resolved by the layout. */
export default function Loading() {
  return <TableSkeleton label="Loading activity" rows={6} />;
}
