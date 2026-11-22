import { TaskBoardSkeleton } from "@/components/skeletons/task-board-skeleton";

/** Shown while the viewer's own tasks load. */
export default function Loading() {
  return <TaskBoardSkeleton />;
}
