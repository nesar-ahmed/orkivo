import type { Metadata } from "next";
import { LabelsScreen, fetchLabels } from "@/features/labels";
import { parsePageParam } from "@/lib/utils/page-param";
import { loadCompany } from "../load-company";

export const dynamic = "force-dynamic";

const LABELS_PER_PAGE = 50;

interface PageProps {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { workspace } = await loadCompany(params);
  return { title: `${workspace.name} · Labels` };
}

/**
 * A company's labels. Every member sees the same list; the read runs as the
 * visitor, so the backend decides membership, not this page.
 */
export default async function CompanyLabelsPage({ params, searchParams }: PageProps) {
  const { workspace, cookie } = await loadCompany(params);
  const page = parsePageParam((await searchParams).page);
  const labels = await fetchLabels(workspace.id, { page, page_size: LABELS_PER_PAGE }, cookie);

  return <LabelsScreen workspace={workspace} labels={labels} />;
}
