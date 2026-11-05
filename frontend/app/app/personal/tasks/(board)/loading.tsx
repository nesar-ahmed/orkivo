import { TaskBoardSkeleton } from "@/components/skeletons/task-board-skeleton";

/**
 * Shown while the board loads. Scoped to the board alone (the `(board)` route
 * group): the task page next to it can answer 404, and a 404 must not be sent
 * after a loading state has already started streaming.
 */
export default function Loading() {
  return <TaskBoardSkeleton />;
}
