import { ProjectsScreen, fetchProjects } from "@/features/projects";
import { readPersonalWorkspace } from "@/features/workspaces";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import { parsePageParam } from "@/lib/utils/page-param";

export const dynamic = "force-dynamic";

export const metadata = { title: "Private projects" };

const PROJECTS_PER_PAGE = 25;

interface PageProps {
  searchParams: Promise<{ page?: string }>;
}

/** Private projects: like private tasks, visible to their owner only. */
export default async function PersonalProjectsPage({ searchParams }: PageProps) {
  const cookie = await getServerCookieHeader();
  const workspace = await readPersonalWorkspace(cookie);
  if (workspace === null) throw new Error("Your private workspace could not be found.");
  const page = parsePageParam((await searchParams).page);
  const projects = await fetchProjects(
    workspace.id,
    { page, page_size: PROJECTS_PER_PAGE },
    cookie,
  );

  return <ProjectsScreen workspace={workspace} projects={projects} />;
}
