/**
 * Typed domain contracts for task dependencies, mirroring
 * backend/app/modules/task_dependencies/schemas.py.
 *
 * A task can wait on other tasks of its own workspace. Dependencies inform rather
 * than enforce: a blocked task can still be started or finished.
 */

import type { TaskCapability, TaskPerson, TaskPriority, TaskStatus } from "@/types/task";

/** A task on either side of a dependency: enough to judge it at a glance. */
export interface DependencyTask {
  id: string;
  title: string;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null;
  assignee: TaskPerson | null;
  /**
   * What the caller may do to *this* task. A link is removed by whoever may
   * change the task that waits, so this says which "Blocking" links are theirs.
   */
  capabilities: TaskCapability[];
}

/** Both directions of one task's dependencies, open work first. */
export interface TaskDependencies {
  /** What the task waits on. */
  blocked_by: DependencyTask[];
  /** What waits on the task. */
  blocking: DependencyTask[];
}
