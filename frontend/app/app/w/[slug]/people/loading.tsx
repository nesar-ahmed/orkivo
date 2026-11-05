import { TableSkeleton } from "@/components/skeletons/task-board-skeleton";

/** Shown while the people list loads. The company itself was resolved by the layout. */
export default function Loading() {
  return <TableSkeleton label="Loading people" />;
}
