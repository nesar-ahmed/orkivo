import type { Metadata } from "next";
import { PersonalOverview, loadPersonalOverview } from "@/features/insights";
import { readMyWorkspacesOnce, readPersonalWorkspace } from "@/features/workspaces";
import { getServerCookieHeader, getViewerToday } from "@/lib/api/server-cookies";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Your work" };

/**
 * The person's own dashboard, and where sign-in lands: their work in every
 * workspace, counted on their own day, with what is late first. The reads run as
 * the visitor, so which workspaces count as theirs is the backend's decision.
 */
export default async function PersonalOverviewPage() {
  const cookie = await getServerCookieHeader();
  const [privateWorkspace, workspaces] = await Promise.all([
    readPersonalWorkspace(cookie),
    readMyWorkspacesOnce(cookie).then((page) => page.items),
  ]);
  if (privateWorkspace === null) {
    // Registration creates it with the account, so this is a data fault.
    throw new Error("Your private workspace could not be found.");
  }
  const data = await loadPersonalOverview(privateWorkspace.id, await getViewerToday(), cookie);

  return <PersonalOverview privateWorkspace={privateWorkspace} workspaces={workspaces} data={data} />;
}
