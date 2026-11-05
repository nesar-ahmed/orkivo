import type { Metadata } from "next";
import { TaskDetail } from "@/features/tasks";
import { hasCapability, workspacePath } from "@/features/workspaces";
import { loadTaskIn } from "../../../../_lib/load-task";
import { loadCompany } from "../../load-company";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ slug: string; taskId: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { taskId } = await params;
  const { workspace, cookie } = await loadCompany(params);
  const task = await loadTaskIn(workspace, taskId, cookie);
  return { title: `${task.title} · ${workspace.name}` };
}

/**
 * One company task, at an address members can share: `/app/w/acme/tasks/<id>`.
 *
 * The company layout has already confirmed membership. A task id the caller
 * cannot reach renders the same 404 as one that never existed, so a link that
 * leaks outside the company shows nothing to anyone outside it.
 */
export default async function CompanyTaskPage({ params }: PageProps) {
  const { taskId } = await params;
  const { workspace, cookie } = await loadCompany(params);
  const task = await loadTaskIn(workspace, taskId, cookie);

  return (
    <TaskDetail
      key={task.id}
      task={task}
      canEdit={hasCapability(workspace, "edit_content")}
      boardPath={workspacePath(workspace, "tasks")}
      shared
    />
  );
}
