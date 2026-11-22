import { LayoutDashboard } from "lucide-react";
import { ButtonLink } from "@/components/ui/button-link";
import { EmptyState } from "@/components/ui/empty-state";
import type { WorkspaceOverviewData } from "@/features/insights/api/overview-data";
import { AttentionList } from "@/features/insights/components/attention-list";
import { headlineTiles } from "@/features/insights/components/headline-tiles";
import { CardLoadError, DashboardCard } from "@/features/insights/components/dashboard-card";
import { PriorityBreakdown } from "@/features/insights/components/priority-breakdown";
import { ProjectProgress } from "@/features/insights/components/project-progress";
import { RecentActivity } from "@/features/insights/components/recent-activity";
import { StatTiles } from "@/features/insights/components/stat-tiles";
import { StatusBreakdown } from "@/features/insights/components/status-breakdown";
import { WorkloadList } from "@/features/insights/components/workload-list";
import { boardHref, tasksLabel } from "@/features/insights/insight-utils";
import { projectTasksHref } from "@/features/projects/project-utils";
import { dayTitle } from "@/features/tasks/task-dates";
import { hasCapability, taskPath, workspacePath } from "@/features/workspaces/workspace-utils";
import type { Workspace } from "@/types/workspace";

/**
 * A company's overview: where its work stands today and who holds it.
 *
 * Laid out the way the strongest work tools' summaries are (Jira's project
 * summary, Asana's and Linear's overviews): the headline numbers first, so
 * anything on fire is seen before anything is read; then how the open work is
 * spread across people next to how all of it splits by status and priority;
 * then the specific tasks that need someone; then projects and the latest
 * activity for context. Nothing is configurable and nothing is a vanity chart:
 * every number is a link to exactly the tasks it counts.
 *
 * Every member sees the same overview --- they can already read every task and
 * who holds it --- and it stays readable in view mode.
 */
export function WorkspaceOverview({
  workspace,
  data,
  viewerId,
}: {
  workspace: Workspace;
  data: WorkspaceOverviewData;
  viewerId: string | null;
}) {
  const { stats } = data;
  const board = (changes: Parameters<typeof boardHref>[1]) => boardHref(workspace, changes);

  return (
    <section aria-labelledby="overview-heading" className="flex flex-col gap-5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 id="overview-heading" className="text-lg font-semibold tracking-tight">
          Overview
        </h2>
        <p className="text-sm text-muted-foreground">Where the work stands on {dayTitle(data.today)}</p>
      </div>

      {stats === null ? (
        <CardLoadError what="This workspace's numbers" />
      ) : stats.totals.total === 0 ? (
        <EmptyState
          icon={<LayoutDashboard />}
          title="Nothing to summarise yet"
          description="Once this workspace has tasks, this overview shows what is open, what is overdue and who holds what."
        >
          {hasCapability(workspace, "edit_content") ? (
            <ButtonLink href={workspacePath(workspace, "tasks")}>Add the first task</ButtonLink>
          ) : null}
        </EmptyState>
      ) : (
        <>
          <StatTiles
            label="This workspace at a glance"
            tiles={headlineTiles(stats.totals, {
              open: board({ status: "open" }),
              inProgress: board({ status: "in_progress" }),
              overdue: board({ due: "overdue" }),
              today: board({ due: "today" }),
              week: board({ due: "week" }),
              done: board({ status: "done" }),
            })}
          />

          <div className="grid gap-4 lg:grid-cols-3">
            <DashboardCard
              id="workload"
              title="Workload"
              description="Open tasks per person, busiest first"
              action={{ href: board({ status: "open" }), label: "All open tasks" }}
              className="lg:col-span-2"
            >
              <WorkloadList
                workload={stats.workload}
                viewerId={viewerId}
                hrefFor={(assignee) => board({ assignee, status: "open" })}
              />
            </DashboardCard>

            <div className="flex flex-col gap-4">
              <DashboardCard id="status" title="Status" description={tasksLabel(stats.totals.total)}>
                <StatusBreakdown counts={stats.totals} hrefFor={(status) => board({ status })} />
              </DashboardCard>
              <DashboardCard id="priority" title="Open by priority">
                <PriorityBreakdown
                  counts={stats.open_by_priority}
                  hrefFor={(priority) => board({ priority, status: "open" })}
                />
              </DashboardCard>
            </div>
          </div>
        </>
      )}

      <DashboardCard
        id="attention"
        title="Needs attention"
        description="Open tasks that are late, due today or due in the next 7 days"
      >
        <div className="grid gap-5 md:grid-cols-2">
          <AttentionList
            title="Overdue"
            tasks={data.overdue?.items ?? null}
            total={data.overdue?.total ?? 0}
            empty="Nothing is overdue."
            hrefFor={(task) => taskPath(workspace, task.id)}
            seeAll={board({ due: "overdue" })}
          />
          <AttentionList
            title="Due soon"
            tasks={data.upcoming?.items ?? null}
            total={data.upcoming?.total ?? 0}
            empty="Nothing is due today or in the next 7 days."
            hrefFor={(task) => taskPath(workspace, task.id)}
            seeAll={board({ view: "calendar" })}
          />
        </div>
      </DashboardCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <DashboardCard
          id="projects"
          title="Projects"
          description="Most open work first"
          action={{ href: workspacePath(workspace, "projects"), label: "All projects" }}
        >
          {data.projects === null ? (
            <CardLoadError what="Projects" />
          ) : (
            <ProjectProgress
              projects={data.projects}
              hrefFor={(project) => projectTasksHref(workspace, project.id)}
            />
          )}
        </DashboardCard>
        <DashboardCard
          id="recent"
          title="Recent activity"
          action={{ href: workspacePath(workspace, "activity"), label: "All activity" }}
        >
          {data.activity === null ? (
            <CardLoadError what="Activity" />
          ) : (
            <RecentActivity workspace={workspace} activity={data.activity} />
          )}
        </DashboardCard>
      </div>
    </section>
  );
}
