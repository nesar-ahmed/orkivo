import type { Metadata } from "next";
import { TaskDiscussion, loadTaskDiscussion } from "@/features/comments";
import { RememberVisit } from "@/features/command-palette";
import { TaskDependenciesSection, loadTaskDependencies } from "@/features/dependencies";
import {
  TaskDetail,
  TaskPage,
  loadTaskChoices,
  taskCan,
  type TaskChoices,
} from "@/features/tasks";
import {
  hasCapability,
  readOnlyReason,
  readPersonalWorkspace,
  taskPath,
  workspacePath,
} from "@/features/workspaces";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import type { Task } from "@/types/task";
import type { Workspace } from "@/types/workspace";
import { loadTaskIn } from "../../../_lib/load-task";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ taskId: string }>;
}

async function load(
  params: PageProps["params"],
): Promise<{
  workspace: Workspace;
  task: Task;
  choices: TaskChoices;
  cookie: string | undefined;
}> {
  const { taskId } = await params;
  const cookie = await getServerCookieHeader();
  const workspace = await readPersonalWorkspace(cookie);
  if (workspace === null) throw new Error("Your private workspace could not be found.");
  const [task, choices] = await Promise.all([
    loadTaskIn(workspace, taskId, cookie),
    loadTaskChoices(workspace.id, cookie),
  ]);
  return { workspace, task, choices, cookie };
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { task } = await load(params);
  return { title: `${task.title} · Private` };
}

/**
 * One private task, with its notes and history. Only its owner is a member of
 * this workspace, so anybody else following the link gets the same 404 as for a
 * task that does not exist.
 */
export default async function PersonalTaskPage({ params }: PageProps) {
  const { workspace, task, choices, cookie } = await load(params);
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
          detail: task.project ? `${"Private workspace"} · ${task.project.name}` : "Private workspace",
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
            shared={false}
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
