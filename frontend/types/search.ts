/**
 * Typed contracts for search across the caller's workspaces, mirroring
 * backend/app/modules/search/schemas.py. Every hit carries its workspace, so a
 * client can link to it without another request.
 */

import type { TaskPriority, TaskStatus } from "@/types/task";
import type { WorkspaceKind } from "@/types/workspace";

export interface SearchWorkspace {
  id: string;
  name: string;
  kind: WorkspaceKind;
  slug: string | null;
}

export interface SearchProjectHit {
  id: string;
  name: string;
  workspace: SearchWorkspace;
}

export interface SearchTaskHit {
  id: string;
  title: string;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null;
  project: { id: string; name: string } | null;
  workspace: SearchWorkspace;
}

/** What matched `query`, per kind, best first. */
export interface SearchResponse {
  query: string;
  workspaces: SearchWorkspace[];
  projects: SearchProjectHit[];
  tasks: SearchTaskHit[];
}
