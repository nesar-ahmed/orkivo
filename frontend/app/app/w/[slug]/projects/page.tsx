import type { Metadata } from "next";
import { ProjectsScreen, fetchProjects } from "@/features/projects";
import { parsePageParam } from "@/lib/utils/page-param";
import { loadCompany } from "../load-company";

export const dynamic = "force-dynamic";

const PROJECTS_PER_PAGE = 25;

interface PageProps {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { workspace } = await loadCompany(params);
  return { title: `${workspace.name} · Projects` };
}

/**
 * A company's projects. Every member sees the same list; the read runs as the
 * visitor, so the backend decides membership, not this page.
 */
export default async function CompanyProjectsPage({ params, searchParams }: PageProps) {
  const { workspace, cookie } = await loadCompany(params);
  const page = parsePageParam((await searchParams).page);
  const projects = await fetchProjects(
    workspace.id,
    { page, page_size: PROJECTS_PER_PAGE },
    cookie,
  );

  return <ProjectsScreen workspace={workspace} projects={projects} />;
}
