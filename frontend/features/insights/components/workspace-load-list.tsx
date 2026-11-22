import Link from "next/link";
import {
  LOAD_ROW,
  LoadBar,
  LoadLegend,
  LoadNumbers,
} from "@/features/insights/components/load-bar";
import { WorkspaceMark } from "@/features/workspaces/components/workspace-switcher";
import type { WorkspaceWorkload } from "@/types/insights";

/**
 * A person's own open work per workspace --- the personal counterpart of a
 * company's workload, answering "where is my work piling up?". Each row opens
 * their list narrowed to that workspace. Workspaces holding none of their work
 * are folded into one line, like idle people on a company's chart.
 */
export function WorkspaceLoadList({
  loads,
  hrefFor,
}: {
  loads: readonly WorkspaceWorkload[];
  hrefFor: (workspaceId: string) => string;
}) {
  const busy = loads.filter((row) => row.counts.open > 0);
  const quiet = loads.filter((row) => row.counts.open === 0);
  const busiest = Math.max(1, ...loads.map((row) => row.counts.open));
  const title = (row: WorkspaceWorkload) =>
    row.workspace.kind === "personal" ? "Private workspace" : row.workspace.name;

  return (
    <div className="flex flex-col gap-3">
      {busy.length > 0 ? (
        <>
          <LoadLegend />
          <ul className="flex flex-col">
            {busy.map((row) => (
              <li key={row.workspace.id}>
                <Link
                  href={hrefFor(row.workspace.id)}
                  className={LOAD_ROW}
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <WorkspaceMark workspace={row.workspace} />
                    <span className="truncate text-sm font-medium text-card-foreground">
                      {title(row)}
                    </span>
                  </span>
                  <LoadBar counts={row.counts} busiest={busiest} />
                  <LoadNumbers counts={row.counts} />
                </Link>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">
          Nothing open anywhere. Tasks assigned to you, and your own to-dos, will show up here.
        </p>
      )}
      {quiet.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          Nothing open in {quiet.map(title).join(", ")}.
        </p>
      ) : null}
    </div>
  );
}
