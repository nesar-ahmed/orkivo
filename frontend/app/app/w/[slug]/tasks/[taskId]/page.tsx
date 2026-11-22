import type { Metadata } from "next";
import { TaskDiscussion, loadTaskDiscussion } from "@/features/comments";
import { RememberVisit } from "@/features/command-palette";
import { TaskDependenciesSection, loadTaskDependencies } from "@/features/dependencies";
import { TaskDetail, TaskPage, loadTaskChoices, taskCan } from "@/features/tasks";
import { hasCapability, readOnlyReason, taskPath, workspacePath } from "@/features/workspaces";
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
 * One company task, at an address members can share: `/app/w/acme/tasks/<id>`,
 * with its comments and history underneath.
 *
 * The company layout has already confirmed membership. A task id the caller
 * cannot reach renders the same 404 as one that never existed, so a link that
 * leaks outside the company shows nothing to anyone outside it.
 */
export default async function CompanyTaskPage({ params }: PageProps) {
  const { taskId } = await params;
  const { workspace, cookie } = await loadCompany(params);
  const [task, choices] = await Promise.all([
    loadTaskIn(workspace, taskId, cookie),
    loadTaskChoices(workspace.id, cookie),
  ]);
  // After the task: its id is the canonical one, and it is known to be readable.
  const [discussion, dependencies] = await Promise.all([
    loadTaskDiscussion(task.id, cookie),
    loadTaskDependencies(task.id, cookie),
  ]);

  return (
    <>
      <RememberVisit
        userId={choices.assignees.viewerId}
        item={{
          kind: "task",
          id: task.id,
          label: task.title,
          detail: task.project ? `${workspace.name} · ${task.project.name}` : workspace.name,
          href: taskPath(workspace, task.id),
          status: task.status,
          workspaceId: workspace.id,
          workspaceKind: workspace.kind,
          workspaceName: workspace.name,
        }}
      />
      <TaskPage
        detail={
          <TaskDetail
            key={task.id}
            task={task}
            boardPath={workspacePath(workspace, "tasks")}
            shared
            choices={choices}
          />
        }
        dependencies={
          <TaskDependenciesSection
            taskId={task.id}
            workspaceId={workspace.id}
            basePath={workspacePath(workspace, "tasks")}
            canEdit={taskCan(task, "edit")}
            canLink={hasCapability(workspace, "edit_content")}
            data={dependencies}
          />
        }
        discussion={
          <TaskDiscussion
            taskId={task.id}
            data={discussion}
            viewerId={choices.assignees.viewerId}
            people={choices.assignees.members}
            canComment={hasCapability(workspace, "comment")}
            readOnly={readOnlyReason(workspace)}
            canModerate={hasCapability(workspace, "manage")}
          />
        }
      />
    </>
  );
}
