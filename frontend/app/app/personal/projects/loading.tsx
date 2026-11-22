import { TableSkeleton } from "@/components/skeletons/task-board-skeleton";

/** Shown while the project list loads. The workspace itself was resolved by the layout. */
export default function Loading() {
  return <TableSkeleton label="Loading projects" />;
}
