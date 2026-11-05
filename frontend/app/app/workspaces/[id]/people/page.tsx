import { notFound, redirect } from "next/navigation";
import { fetchWorkspace, workspacePath } from "@/features/workspaces";
import { ApiError } from "@/lib/api/client";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import type { Workspace } from "@/types/workspace";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * The old, id-based address of a company's people page.
 *
 * Companies are addressed by name now (`/app/w/<slug>/people`). Links that were
 * shared before keep working: a member is forwarded, and anybody else gets the
 * same 404 as for an id that never existed.
 */
export default async function LegacyPeoplePage({ params }: PageProps) {
  const { id: workspaceId } = await params;
  if (!UUID_PATTERN.test(workspaceId)) notFound();

  let workspace: Workspace;
  try {
    workspace = await fetchWorkspace(workspaceId, await getServerCookieHeader());
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  redirect(workspacePath(workspace, "people"));
}
