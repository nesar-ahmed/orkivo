/**
 * Server-side reads for the two dashboards: a workspace's overview, and a
 * person's own (the private workspace's overview).
 *
 * Everything is read in parallel, as the visitor, on their own day
 * (`getViewerToday`), and each block is optional: if one read fails, its card
 * says so and the rest of the dashboard still renders --- the same way a board
 * still renders when its pickers could not load.
 *
 * The "needs attention" lists are ordinary task lists (soonest due first, five
 * each), so each dashboard row is exactly the task its list and board show.
 */

import { fetchWorkspaceActivity } from "@/features/activity/api/activity-queries";
import { fetchMyStats, fetchWorkspaceStats } from "@/features/insights/api/insight-queries";
import { fetchProjects } from "@/features/projects/api/project-queries";
import {
  fetchMyTasks,
  fetchTasks,
  type MyTaskListParams,
} from "@/features/tasks/api/task-queries";
import { addDays } from "@/features/tasks/task-dates";
import type { ActivityListResponse } from "@/types/activity";
import type { MyStats, WorkspaceStats } from "@/types/insights";
import type { ProjectSummary } from "@/types/project";
import type { Task } from "@/types/task";

/** How many tasks each "needs attention" list shows before "See all". */
export const ATTENTION_ROWS = 5;
/** How many recent events the activity card shows. */
export const RECENT_EVENTS = 6;
/** A workspace holds at most this many projects on one page, which is all a card needs. */
const PROJECTS_PAGE_SIZE = 100;

/** One block of a dashboard: its data, or `null` when it could not be read. */
type Block<T> = T | null;

interface AttentionData {
  /** Open work due before today, soonest first. */
  readonly overdue: Block<{ items: Task[]; total: number }>;
  /** Open work due today or in the next seven days, soonest first. */
  readonly upcoming: Block<{ items: Task[]; total: number }>;
}

export interface WorkspaceOverviewData extends AttentionData {
  readonly today: string;
  readonly stats: Block<WorkspaceStats>;
  readonly projects: Block<ProjectSummary[]>;
  readonly activity: Block<ActivityListResponse>;
}

export interface PersonalOverviewData extends AttentionData {
  readonly today: string;
  readonly stats: Block<MyStats>;
  /** The private workspace's projects and activity. */
  readonly projects: Block<ProjectSummary[]>;
  readonly activity: Block<ActivityListResponse>;
}

/** The windows the attention lists read, on `today`. */
function attentionWindows(today: string): { overdue: MyTaskListParams; upcoming: MyTaskListParams } {
  const common = { status: "open", order: "due", page_size: ATTENTION_ROWS } as const;
  return {
    overdue: { ...common, due_to: addDays(today, -1) },
    upcoming: { ...common, due_from: today, due_to: addDays(today, 7) },
  };
}

function optional<T>(read: Promise<T>): Promise<Block<T>> {
  return read.catch(() => null);
}

export async function loadWorkspaceOverview(
  workspaceId: string,
  today: string,
  cookie: string | undefined,
): Promise<WorkspaceOverviewData> {
  const windows = attentionWindows(today);
  const [stats, overdue, upcoming, projects, activity] = await Promise.all([
    optional(fetchWorkspaceStats(workspaceId, today, cookie)),
    optional(fetchTasks(workspaceId, windows.overdue, cookie)),
    optional(fetchTasks(workspaceId, windows.upcoming, cookie)),
    optional(
      fetchProjects(workspaceId, { page_size: PROJECTS_PAGE_SIZE }, cookie).then(
        (page) => page.items,
      ),
    ),
    optional(fetchWorkspaceActivity(workspaceId, { page_size: RECENT_EVENTS }, cookie)),
  ]);
  return { today, stats, overdue, upcoming, projects, activity };
}

export async function loadPersonalOverview(
  privateWorkspaceId: string,
  today: string,
  cookie: string | undefined,
): Promise<PersonalOverviewData> {
  const windows = attentionWindows(today);
  const [stats, overdue, upcoming, projects, activity] = await Promise.all([
    optional(fetchMyStats(today, cookie)),
    optional(fetchMyTasks(windows.overdue, cookie)),
    optional(fetchMyTasks(windows.upcoming, cookie)),
    optional(
      fetchProjects(privateWorkspaceId, { page_size: PROJECTS_PAGE_SIZE }, cookie).then(
        (page) => page.items,
      ),
    ),
    optional(fetchWorkspaceActivity(privateWorkspaceId, { page_size: RECENT_EVENTS }, cookie)),
  ]);
  return { today, stats, overdue, upcoming, projects, activity };
}
