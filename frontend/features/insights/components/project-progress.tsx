import Link from "next/link";
import { FolderKanban } from "lucide-react";
import { percent, share } from "@/features/insights/insight-utils";
import type { ProjectSummary } from "@/types/project";

/** How many projects the card lists; the projects page lists them all. */
const SHOWN = 5;

/**
 * Projects by how much is left in them --- the ones with the most open work
 * first --- each with a progress bar (done out of all its tasks) and a way into
 * its tasks. Projects without tasks stay on the projects page.
 */
export function ProjectProgress({
  projects,
  hrefFor,
}: {
  projects: readonly ProjectSummary[];
  hrefFor: (project: ProjectSummary) => string;
}) {
  const active = projects
    .filter((project) => project.task_count > 0)
    .sort((a, b) => b.open_task_count - a.open_task_count || a.name.localeCompare(b.name))
    .slice(0, SHOWN);

  if (active.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No project holds any tasks yet. File tasks under a project to follow its progress here.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-1">
      {active.map((project) => {
        const done = project.task_count - project.open_task_count;
        return (
          <li key={project.id}>
            <Link
              href={hrefFor(project)}
              className="-mx-2 flex flex-col gap-1.5 rounded-md px-2 py-2 hover:bg-muted"
            >
              <span className="flex items-center gap-2 text-sm">
                <FolderKanban aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate font-medium text-card-foreground">
                  {project.name}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                  {project.open_task_count} open · {percent(done, project.task_count)}% done
                </span>
              </span>
              <span aria-hidden="true" className="h-1.5 overflow-hidden rounded-full bg-muted">
                <span
                  className="block h-full rounded-full bg-status-done"
                  style={{ width: share(done, project.task_count) }}
                />
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
