import type { Metadata } from "next";
import { readCurrentUserOnce } from "@/features/auth";
import { WorkspaceOverview, loadWorkspaceOverview } from "@/features/insights";
import { getViewerToday } from "@/lib/api/server-cookies";
import { loadCompany } from "../load-company";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { workspace } = await loadCompany(params);
  return { title: `${workspace.name} · Overview` };
}

/**
 * A company's overview, and where its address lands: what is open, what is late,
 * who holds what. Every member sees the same one; the reads run as the visitor,
 * on their own day, so the backend decides membership and "overdue" means their
 * calendar's.
 */
export default async function CompanyOverviewPage({ params }: PageProps) {
  const { workspace, cookie } = await loadCompany(params);
  const [data, viewer] = await Promise.all([
    loadWorkspaceOverview(workspace.id, await getViewerToday(), cookie),
    // Already read by the `/app` layout on this request, so this costs nothing.
    readCurrentUserOnce(cookie).catch(() => null),
  ]);

  return <WorkspaceOverview workspace={workspace} data={data} viewerId={viewer?.id ?? null} />;
}
