/**
 * Per-request workspace reads for server components.
 *
 * The app shell needs the caller's workspaces for the switcher, and a workspace
 * page needs the one it shows. `cache` deduplicates those reads per render pass,
 * so a layout and the page below it cost one API call and cannot disagree about
 * the same request (the same pattern as `readCurrentUserOnce`).
 */

import { cache } from "react";
import {
  fetchMyWorkspaces,
  fetchWorkspaceBySlug,
} from "@/features/workspaces/api/workspace-queries";
import type { Workspace, WorkspaceListResponse } from "@/types/workspace";

/** Enough for the switcher; someone in more companies than this pages on /app/workspaces. */
const SWITCHER_PAGE_SIZE = 100;

export const readMyWorkspacesOnce = cache(
  (cookie?: string): Promise<WorkspaceListResponse> =>
    fetchMyWorkspaces({ page_size: SWITCHER_PAGE_SIZE }, cookie),
);

export const readWorkspaceBySlugOnce = cache(
  (slug: string, cookie?: string): Promise<Workspace> => fetchWorkspaceBySlug(slug, cookie),
);

/**
 * The caller's private workspace. Registration creates it with the account, and
 * the backend lists it first, so it is always on the first page.
 */
export async function readPersonalWorkspace(cookie?: string): Promise<Workspace | null> {
  const workspaces = await readMyWorkspacesOnce(cookie);
  return workspaces.items.find((workspace) => workspace.kind === "personal") ?? null;
}
