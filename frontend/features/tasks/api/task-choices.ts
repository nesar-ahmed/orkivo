/**
 * Server-side read of what a task in one workspace can be assigned to, filed
 * under and tagged with: the workspace's people, its projects and its labels.
 *
 * All three are reduced to names and ids (and a label's color) before they reach
 * a client component. They are conveniences for pickers, filters and board lanes
 * only: if a read fails, the board still renders (offering "me", "unassigned",
 * "no project" and "no labels"), and every save is re-checked by the API against
 * the workspace. A workspace holds at most 100 labels, so one page is all of them.
 *
 * Cached per request like the other `…Once` reads, so a page and its
 * `generateMetadata` share one pair of reads.
 */

import { cache } from "react";
import { readCurrentUserOnce } from "@/features/auth";
import { fetchLabels } from "@/features/labels/api/label-queries";
import { fetchProjects } from "@/features/projects/api/project-queries";
import type { AssigneeOptions, TaskChoices } from "@/features/tasks/task-utils";
import { fetchMembers } from "@/features/workspaces/api/workspace-queries";
import type { TaskLabel, TaskProject } from "@/types/task";

/** The API's page-size ceiling. Larger lists page on their own screens. */
const CHOICES_PAGE_SIZE = 100;

export const loadTaskChoices = cache(async function loadTaskChoices(
  workspaceId: string,
  cookie: string | undefined,
): Promise<TaskChoices> {
  const [assignees, projects, labels] = await Promise.all([
    loadAssigneeOptions(workspaceId, cookie),
    loadProjectOptions(workspaceId, cookie),
    loadLabelOptions(workspaceId, cookie),
  ]);
  return { assignees, projects, labels };
});

async function loadAssigneeOptions(
  workspaceId: string,
  cookie: string | undefined,
): Promise<AssigneeOptions> {
  const [members, viewer] = await Promise.all([
    fetchMembers(workspaceId, { page_size: CHOICES_PAGE_SIZE }, cookie)
      .then((page) => page.items)
      .catch(() => []),
    // Already read by the `/app` layout on this request, so this costs nothing.
    readCurrentUserOnce(cookie).catch(() => null),
  ]);
  return {
    members: members
      .map((member) => ({ id: member.user_id, display_name: member.display_name }))
      .sort((a, b) => a.display_name.localeCompare(b.display_name)),
    viewerId: viewer?.id ?? null,
  };
}

/** Alphabetical, as the API lists them; also the order of the board's lanes. */
async function loadProjectOptions(
  workspaceId: string,
  cookie: string | undefined,
): Promise<TaskProject[]> {
  try {
    const page = await fetchProjects(workspaceId, { page_size: CHOICES_PAGE_SIZE }, cookie);
    return page.items.map((project) => ({ id: project.id, name: project.name }));
  } catch {
    return [];
  }
}

/** Alphabetical, as the API lists them; also the order of every label picker. */
async function loadLabelOptions(
  workspaceId: string,
  cookie: string | undefined,
): Promise<TaskLabel[]> {
  try {
    const page = await fetchLabels(workspaceId, { page_size: CHOICES_PAGE_SIZE }, cookie);
    return page.items.map((label) => ({ id: label.id, name: label.name, color: label.color }));
  } catch {
    return [];
  }
}
