/**
 * Typed contracts for dashboards, mirroring
 * backend/app/modules/insights/schemas.py.
 *
 * Every number is counted by the backend on the request that shows it, on the
 * viewer's own day (`today`), from the same tasks the lists show.
 */

import type { WorkspaceKind, WorkspaceRole } from "@/types/workspace";

/**
 * How much work a group holds. `open` is everything not done. The due-date
 * counts cover open work only: due before `today`, on it, and in the seven days
 * after it --- the buckets a person's own list is grouped into.
 */
export interface TaskCounts {
  total: number;
  todo: number;
  in_progress: number;
  done: number;
  open: number;
  overdue: number;
  due_today: number;
  due_next_7_days: number;
}

/** Open work per priority. */
export interface PriorityCounts {
  high: number;
  medium: number;
  low: number;
}

/** One member's share; `person` and `role` are `null` on the row for unassigned work. */
export interface MemberWorkload {
  person: { id: string; display_name: string } | null;
  role: WorkspaceRole | null;
  counts: TaskCounts;
}

/** A workspace's dashboard. `workload` lists every member, busiest first, then unassigned. */
export interface WorkspaceStats {
  workspace_id: string;
  today: string;
  totals: TaskCounts;
  open_by_priority: PriorityCounts;
  workload: MemberWorkload[];
}

/** How much of a person's own work lives in one of their workspaces. */
export interface WorkspaceWorkload {
  workspace: { id: string; name: string; kind: WorkspaceKind; slug: string | null };
  counts: TaskCounts;
}

/** A person's own dashboard: their work everywhere (what My tasks lists), per workspace. */
export interface MyStats {
  today: string;
  totals: TaskCounts;
  open_by_priority: PriorityCounts;
  by_workspace: WorkspaceWorkload[];
}
