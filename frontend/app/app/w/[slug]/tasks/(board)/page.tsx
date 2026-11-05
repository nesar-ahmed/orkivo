import type { Metadata } from "next";
import { TaskBoard, loadTaskView, parseTaskQuery } from "@/features/tasks";
import { workspacePath } from "@/features/workspaces";
import { loadCompany } from "../../load-company";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { workspace } = await loadCompany(params);
  return { title: `${workspace.name} · Tasks` };
}

/**
 * A company's shared tasks, as a list or a board (`?view=board`), filtered by the
 * URL. Every member sees and edits the same tasks; the reads run as the visitor,
 * so the backend decides membership, not this page.
 */
export default async function CompanyTasksPage({ params, searchParams }: PageProps) {
  const { workspace, cookie } = await loadCompany(params);
  const query = parseTaskQuery(await searchParams);
  const data = await loadTaskView(workspace.id, query, workspacePath(workspace, "tasks"), cookie);

  return <TaskBoard workspace={workspace} query={query} data={data} />;
}
