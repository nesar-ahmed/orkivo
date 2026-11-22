import { Sparkles } from "lucide-react";
import { ButtonLink } from "@/components/ui/button-link";
import { EmptyState } from "@/components/ui/empty-state";
import type { PersonalOverviewData } from "@/features/insights/api/overview-data";
import { AttentionList } from "@/features/insights/components/attention-list";
import { CardLoadError, DashboardCard } from "@/features/insights/components/dashboard-card";
import { headlineTiles } from "@/features/insights/components/headline-tiles";
import { PriorityBreakdown } from "@/features/insights/components/priority-breakdown";
import { ProjectProgress } from "@/features/insights/components/project-progress";
import { RecentActivity } from "@/features/insights/components/recent-activity";
import { StatTiles } from "@/features/insights/components/stat-tiles";
import { StatusBreakdown } from "@/features/insights/components/status-breakdown";
import { WorkspaceLoadList } from "@/features/insights/components/workspace-load-list";
import { myTasksHref, tasksLabel } from "@/features/insights/insight-utils";
import { MY_TASKS_PATH } from "@/features/my-tasks/my-task-query";
import { projectTasksHref } from "@/features/projects/project-utils";
import { dayTitle } from "@/features/tasks/task-dates";
import { taskPath, workspacePath } from "@/features/workspaces/workspace-utils";
import type { Task } from "@/types/task";
import type { Workspace } from "@/types/workspace";

/**
 * A person's own dashboard, on their private workspace's overview: *their* work,
 * wherever it lives.
 *
 * Personal home pages in work tools (Asana's Home, Jira's "Your work", ClickUp's
 * "My Work") share one idea: start from what is yours, across every space, and
 * surface what is late before anything else. So this counts exactly what "My
 * tasks" lists --- everything assigned to them in any workspace, plus their own
 * private to-dos --- with the same headline numbers and breakdowns as a company's
 * overview, "by workspace" in place of "by person", and their private
 * workspace's projects and activity underneath. Every number opens its list.
 */
export function PersonalOverview({
  privateWorkspace,
  workspaces,
  data,
}: {
  privateWorkspace: Workspace;
  /** The caller's workspaces, to say where each task lives and link to it there. */
  workspaces: readonly Workspace[];
  data: PersonalOverviewData;
}) {
  const { stats } = data;
  const byId = new Map(workspaces.map((workspace) => [workspace.id, workspace]));
  const taskHref = (task: Task) => {
    const home = byId.get(task.workspace_id);
    return home ? taskPath(home, task.id) : MY_TASKS_PATH;
  };
  const whereIs = (task: Task) => {
    const home = byId.get(task.workspace_id);
    return !home ? "Another workspace" : home.kind === "personal" ? "Private" : home.name;
  };

  return (
    <section aria-labelledby="overview-heading" className="flex flex-col gap-5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 id="overview-heading" className="text-lg font-semibold tracking-tight">
          Your work
        </h2>
        <p className="text-sm text-muted-foreground">
          Across all your workspaces, on {dayTitle(data.today)}
        </p>
      </div>

      {stats === null ? (
        <CardLoadError what="Your numbers" />
      ) : stats.totals.total === 0 ? (
        <EmptyState
          icon={<Sparkles />}
          title="A clean slate"
          description="Add your own to-dos here, or get assigned work in a company. This page then shows what is open, what is late and where it all lives."
        >
          <ButtonLink href={workspacePath(privateWorkspace, "tasks")}>Add a task</ButtonLink>
        </EmptyState>
      ) : (
        <>
          <StatTiles
            label="Your work at a glance"
            tiles={headlineTiles(stats.totals, {
              open: myTasksHref(),
              inProgress: myTasksHref({ status: "in_progress" }),
              overdue: myTasksHref({ due: "overdue" }),
              today: myTasksHref({ due: "today" }),
              week: myTasksHref({ due: "week" }),
              done: myTasksHref({ status: "done" }),
            })}
          />

          {/* Top-aligned: a person is in a few workspaces, not a company's worth of people. */}
          <div className="grid items-start gap-4 lg:grid-cols-3">
            <DashboardCard
              id="by-workspace"
              title="By workspace"
              description="Where your open work lives"
              action={{ href: MY_TASKS_PATH, label: "My tasks" }}
              className="lg:col-span-2"
            >
              <WorkspaceLoadList
                loads={stats.by_workspace}
                hrefFor={(workspace) => myTasksHref({ workspace })}
              />
            </DashboardCard>
            <div className="flex flex-col gap-4">
              <DashboardCard id="status" title="Status" description={tasksLabel(stats.totals.total)}>
                <StatusBreakdown
                  counts={stats.totals}
                  hrefFor={(status) => myTasksHref({ status })}
                />
              </DashboardCard>
              <DashboardCard id="priority" title="Open by priority">
                <PriorityBreakdown
                  counts={stats.open_by_priority}
                  hrefFor={(priority) => myTasksHref({ priority })}
                />
              </DashboardCard>
            </div>
          </div>
        </>
      )}

      <DashboardCard
        id="attention"
        title="Needs attention"
        description="Your open tasks that are late, due today or due in the next 7 days"
      >
        <div className="grid gap-5 md:grid-cols-2">
          <AttentionList
            title="Overdue"
            tasks={data.overdue?.items ?? null}
            total={data.overdue?.total ?? 0}
            empty="Nothing of yours is overdue."
            hrefFor={taskHref}
            seeAll={myTasksHref({ due: "overdue" })}
            where={whereIs}
            showAssignee={false}
          />
          <AttentionList
            title="Due soon"
            tasks={data.upcoming?.items ?? null}
            total={data.upcoming?.total ?? 0}
            empty="Nothing of yours is due today or in the next 7 days."
            hrefFor={taskHref}
            seeAll={myTasksHref({ view: "calendar" })}
            where={whereIs}
            showAssignee={false}
          />
        </div>
      </DashboardCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <DashboardCard
          id="projects"
          title="Private projects"
          description="Only you can see these"
          action={{ href: workspacePath(privateWorkspace, "projects"), label: "All projects" }}
        >
          {data.projects === null ? (
            <CardLoadError what="Projects" />
          ) : (
            <ProjectProgress
              projects={data.projects}
              hrefFor={(project) => projectTasksHref(privateWorkspace, project.id)}
            />
          )}
        </DashboardCard>
        <DashboardCard
          id="recent"
          title="Recent activity"
          description="In your private workspace"
          action={{ href: workspacePath(privateWorkspace, "activity"), label: "All activity" }}
        >
          {data.activity === null ? (
            <CardLoadError what="Activity" />
          ) : (
            <RecentActivity workspace={privateWorkspace} activity={data.activity} />
          )}
        </DashboardCard>
      </div>
    </section>
  );
}
