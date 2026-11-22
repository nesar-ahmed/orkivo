/**
 * Everything the command palette can offer, as one shape: pages to go to, recent
 * items, and what a search found.
 *
 * Pages come from the same sections the sidebar shows for the workspace the
 * person is in (`workspaceSections`), so the palette never offers a page the
 * sidebar would not. Search hits are built into addresses exactly as their own
 * pages build them (`taskPath`, `projectTasksHref`, `workspacePath`).
 */

import type { RecentItem } from "@/features/command-palette/recent-items";
import { projectTasksHref } from "@/features/projects/project-utils";
import {
  WORKSPACE_HOME_SECTION,
  taskPath,
  workspacePath,
  workspaceSections,
  type WorkspaceSection,
} from "@/features/workspaces/workspace-utils";
import type { User } from "@/types/auth";
import type { SearchResponse, SearchWorkspace } from "@/types/search";
import type { TaskStatus } from "@/types/task";
import type { Workspace, WorkspaceKind } from "@/types/workspace";

export type PaletteGroup = "recent" | "pages" | "workspaces" | "projects" | "tasks";

export const GROUP_LABELS: Record<PaletteGroup, string> = {
  recent: "Recent",
  pages: "Go to",
  workspaces: "Workspaces",
  projects: "Projects",
  tasks: "Tasks",
};

/** What an item is, which decides its icon. */
export type PaletteItemKind = "page" | "workspace" | "project" | "task";

export interface PaletteItem {
  /** Unique across the palette: `<group>:<kind>:<id>`. */
  readonly key: string;
  readonly group: PaletteGroup;
  readonly kind: PaletteItemKind;
  readonly label: string;
  /** Shown beside the label, muted: where it lives. */
  readonly detail?: string;
  readonly href: string;
  /** Workspaces, projects and tasks: what to remember when it is opened. */
  readonly recent?: RecentItem;
  readonly status?: TaskStatus;
  readonly workspace?: { kind: WorkspaceKind; name: string };
  /** Extra words a page answers to ("board", "kanban" for tasks). */
  readonly keywords?: string;
}

const SECTION_LABELS: Record<WorkspaceSection, string> = {
  overview: "Overview",
  tasks: "Tasks",
  projects: "Projects",
  labels: "Labels",
  activity: "Activity",
  people: "People",
  automations: "Automations",
};

const SECTION_KEYWORDS: Partial<Record<WorkspaceSection, string>> = {
  overview: "dashboard home stats workload",
  tasks: "board list calendar kanban",
  people: "members team invite roles",
  automations: "rules notify",
};

/** A workspace's name as people see it: a private one is never "Ana's workspace". */
export function workspaceLabel(workspace: Pick<Workspace, "kind" | "name">): string {
  return workspace.kind === "personal" ? "Private workspace" : workspace.name;
}

/** The pages of the workspace the person is in, then the product's own pages. */
export function pageItems(current: Workspace | null, user: Pick<User, "platform_role">): PaletteItem[] {
  const inWorkspace: PaletteItem[] = current
    ? workspaceSections(current.kind).map((section) => ({
        key: `pages:page:${section}`,
        group: "pages",
        kind: "page",
        label: SECTION_LABELS[section],
        detail: workspaceLabel(current),
        href: workspacePath(current, section),
        keywords: SECTION_KEYWORDS[section],
      }))
    : [];
  const product: PaletteItem[] = [
    { label: "My tasks", href: "/app/my-tasks", keywords: "assigned to me mine todo" },
    { label: "Workspaces", href: "/app/workspaces", keywords: "companies switch create" },
    { label: "Invitations & profile", href: "/app/profile", keywords: "account settings theme" },
    ...(user.platform_role === "operator"
      ? [{ label: "Platform", href: "/app/platform/tenants", keywords: "tenants accounts operator" }]
      : []),
  ].map((page) => ({ ...page, key: `pages:page:${page.href}`, group: "pages", kind: "page" }));
  return [...inWorkspace, ...product];
}

/** Whether `item` answers to what was typed: every word appears in its text. */
export function matchesQuery(item: PaletteItem, query: string): boolean {
  const haystack = `${item.label} ${item.detail ?? ""} ${item.keywords ?? ""}`.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word));
}

/** The person's workspaces, as items. */
export function workspaceItems(workspaces: readonly Workspace[]): PaletteItem[] {
  return workspaces.map((workspace) => workspaceItem(workspace, "workspaces"));
}

function workspaceItem(workspace: SearchWorkspace, group: PaletteGroup): PaletteItem {
  const label = workspaceLabel(workspace);
  const href = workspacePath(workspace, WORKSPACE_HOME_SECTION);
  return {
    key: `${group}:workspace:${workspace.id}`,
    group,
    kind: "workspace",
    label,
    detail: workspace.kind === "team" ? `/${workspace.slug}` : "Only you",
    href,
    workspace: { kind: workspace.kind, name: workspace.name },
    recent: {
      kind: "workspace",
      id: workspace.id,
      label,
      href,
      workspaceId: workspace.id,
      workspaceKind: workspace.kind,
      workspaceName: workspace.name,
    },
  };
}

/** What a search found, in the order the palette lists it. */
export function searchItems(results: SearchResponse): PaletteItem[] {
  const tasks: PaletteItem[] = results.tasks.map((task) => {
    const where = workspaceLabel(task.workspace);
    const detail = task.project ? `${where} · ${task.project.name}` : where;
    const href = taskPath(task.workspace, task.id);
    return {
      key: `tasks:task:${task.id}`,
      group: "tasks",
      kind: "task",
      label: task.title,
      detail,
      href,
      status: task.status,
      recent: {
        kind: "task",
        id: task.id,
        label: task.title,
        detail,
        href,
        status: task.status,
        workspaceId: task.workspace.id,
        workspaceKind: task.workspace.kind,
        workspaceName: task.workspace.name,
      },
    };
  });
  const projects: PaletteItem[] = results.projects.map((project) => {
    const detail = workspaceLabel(project.workspace);
    const href = projectTasksHref(project.workspace, project.id);
    return {
      key: `projects:project:${project.id}`,
      group: "projects",
      kind: "project",
      label: project.name,
      detail,
      href,
      recent: {
        kind: "project",
        id: project.id,
        label: project.name,
        detail,
        href,
        workspaceId: project.workspace.id,
        workspaceKind: project.workspace.kind,
        workspaceName: project.workspace.name,
      },
    };
  });
  const workspaces = results.workspaces.map((workspace) => workspaceItem(workspace, "workspaces"));
  return [...tasks, ...projects, ...workspaces];
}

/** Recently opened items, as the palette offers them before anything is typed. */
export function recentItems(recent: readonly RecentItem[]): PaletteItem[] {
  return recent.map((item) => ({
    key: `recent:${item.kind}:${item.id}`,
    group: "recent",
    kind: item.kind,
    label: item.label,
    detail: item.detail,
    href: item.href,
    status: item.status,
    workspace: { kind: item.workspaceKind, name: item.workspaceName },
    recent: item,
  }));
}
