import type { Metadata } from "next";
import { ActivityFeed, fetchWorkspaceActivity } from "@/features/activity";
import { parsePageParam } from "@/lib/utils/page-param";
import { loadCompany } from "../load-company";

export const dynamic = "force-dynamic";

const EVENTS_PER_PAGE = 30;

interface PageProps {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { workspace } = await loadCompany(params);
  return { title: `${workspace.name} · Activity` };
}

/**
 * What happened in a company, newest first --- including tasks deleted since.
 * Every member reads the same feed; the read runs as the visitor.
 */
export default async function CompanyActivityPage({ params, searchParams }: PageProps) {
  const { workspace, cookie } = await loadCompany(params);
  const page = parsePageParam((await searchParams).page);
  const activity = await fetchWorkspaceActivity(
    workspace.id,
    { page, page_size: EVENTS_PER_PAGE },
    cookie,
  );

  return <ActivityFeed workspace={workspace} activity={activity} />;
}
