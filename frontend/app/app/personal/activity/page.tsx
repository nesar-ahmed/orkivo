import { ActivityFeed, fetchWorkspaceActivity } from "@/features/activity";
import { readPersonalWorkspace } from "@/features/workspaces";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import { parsePageParam } from "@/lib/utils/page-param";

export const dynamic = "force-dynamic";

export const metadata = { title: "Private activity" };

const EVENTS_PER_PAGE = 30;

interface PageProps {
  searchParams: Promise<{ page?: string }>;
}

/** What happened in the private workspace: only its owner ever sees this. */
export default async function PersonalActivityPage({ searchParams }: PageProps) {
  const cookie = await getServerCookieHeader();
  const workspace = await readPersonalWorkspace(cookie);
  if (workspace === null) throw new Error("Your private workspace could not be found.");
  const page = parsePageParam((await searchParams).page);
  const activity = await fetchWorkspaceActivity(
    workspace.id,
    { page, page_size: EVENTS_PER_PAGE },
    cookie,
  );

  return <ActivityFeed workspace={workspace} activity={activity} />;
}
