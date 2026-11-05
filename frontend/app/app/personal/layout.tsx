import type { ReactNode } from "react";
import { WorkspaceHeader, readPersonalWorkspace } from "@/features/workspaces";
import { getServerCookieHeader } from "@/lib/api/server-cookies";

export const dynamic = "force-dynamic";

/**
 * The caller's private workspace. It has no address to share: the path is the
 * same for everyone, and it always means *your own* workspace.
 */
export default async function PersonalLayout({ children }: { children: ReactNode }) {
  const cookie = await getServerCookieHeader();
  const workspace = await readPersonalWorkspace(cookie);
  if (workspace === null) {
    // Registration creates it with the account, so this is a data fault.
    throw new Error("Your private workspace could not be found.");
  }

  return (
    <div className="flex flex-col gap-6">
      <WorkspaceHeader workspace={workspace} />
      {children}
    </div>
  );
}
