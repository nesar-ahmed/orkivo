import { LabelsScreen, fetchLabels } from "@/features/labels";
import { readPersonalWorkspace } from "@/features/workspaces";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import { parsePageParam } from "@/lib/utils/page-param";

export const dynamic = "force-dynamic";

export const metadata = { title: "Private labels" };

const LABELS_PER_PAGE = 50;

interface PageProps {
  searchParams: Promise<{ page?: string }>;
}

/** Private labels: like private tasks, visible to their owner only. */
export default async function PersonalLabelsPage({ searchParams }: PageProps) {
  const cookie = await getServerCookieHeader();
  const workspace = await readPersonalWorkspace(cookie);
  if (workspace === null) throw new Error("Your private workspace could not be found.");
  const page = parsePageParam((await searchParams).page);
  const labels = await fetchLabels(workspace.id, { page, page_size: LABELS_PER_PAGE }, cookie);

  return <LabelsScreen workspace={workspace} labels={labels} />;
}
