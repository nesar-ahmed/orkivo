import { MyTasksScreen, loadMyTaskView, parseMyTaskQuery } from "@/features/my-tasks";
import { loadTaskChoices } from "@/features/tasks";
import { NO_TASK_CHOICES } from "@/features/tasks/task-utils";
import { readMyWorkspacesOnce } from "@/features/workspaces";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import type { Workspace } from "@/types/workspace";

export const dynamic = "force-dynamic";

export const metadata = { title: "My tasks" };

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * The viewer's own work across every workspace they are in. Which workspaces
 * count, and which tasks are theirs, is decided by the backend on this request;
 * the workspace list (already read by the `/app` layout) only names them and says
 * what the viewer may do in each.
 */
export default async function MyTasksPage({ searchParams }: PageProps) {
  const cookie = await getServerCookieHeader();
  const query = parseMyTaskQuery(await searchParams);
  let workspaces: Workspace[] = [];
  try {
    workspaces = (await readMyWorkspacesOnce(cookie)).items;
  } catch {
    // The list still renders; rows then link to the workspaces page instead.
    workspaces = [];
  }
  const personal = workspaces.find((workspace) => workspace.kind === "personal") ?? null;
  const [data, choices] = await Promise.all([
    loadMyTaskView(query, cookie),
    personal ? loadTaskChoices(personal.id, cookie) : Promise.resolve(NO_TASK_CHOICES),
  ]);

  return (
    <MyTasksScreen
      query={query}
      data={data}
      workspaces={workspaces}
      personal={personal}
      choices={choices}
    />
  );
}
