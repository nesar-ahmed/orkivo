import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { formatAccountDate } from "@/features/users/user-utils";
import {
  WORKSPACE_KIND_LABELS,
  WORKSPACE_ROLE_BADGES,
  WORKSPACE_ROLE_LABELS,
  WORKSPACE_STATUS_BADGES,
  WORKSPACE_STATUS_LABELS,
  workspacePath,
} from "@/features/workspaces/workspace-utils";
import type { Workspace } from "@/types/workspace";

/**
 * The tenants the caller belongs to.
 *
 * A personal workspace gets no people page: nobody can be invited into it, which
 * the backend also enforces --- the UI does not offer what the API refuses
 * (architecture doc 8.2).
 */
export function WorkspaceList({ teams }: { teams: Workspace[] }) {
  const shared = teams.filter((team) => team.kind === "team");

  return (
    <ul className="flex flex-col gap-3" aria-label="Your workspaces">
      {teams.map((team) => (
        <li
          key={team.id}
          className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-sm"
        >
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-card-foreground">
              {team.name}
              {team.slug ? (
                <span className="ml-2 font-mono text-xs text-muted-foreground">/{team.slug}</span>
              ) : null}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {WORKSPACE_KIND_LABELS[team.kind]} · since{" "}
              {formatAccountDate(team.created_at)}
            </p>
          </div>

          <Badge variant={WORKSPACE_ROLE_BADGES[team.my_role]}>
            {WORKSPACE_ROLE_LABELS[team.my_role]}
          </Badge>
          {team.status !== "active" ? (
            <Badge variant={WORKSPACE_STATUS_BADGES[team.status]}>
              {WORKSPACE_STATUS_LABELS[team.status]}
            </Badge>
          ) : null}

          <Link
            href={workspacePath(team, "tasks")}
            className="inline-flex h-8 items-center justify-center rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:bg-primary-hover"
          >
            Tasks
          </Link>
          {team.kind === "team" ? (
            <Link
              href={workspacePath(team, "people")}
              className="inline-flex h-8 items-center justify-center rounded-md border border-border bg-card px-3 text-xs font-medium text-card-foreground hover:bg-muted"
            >
              People
            </Link>
          ) : (
            <span className="text-xs text-muted-foreground">Only you</span>
          )}
        </li>
      ))}

      {shared.length === 0 ? (
        <li>
          <EmptyState
            title="No companies yet"
            description="Your private workspace holds your own tasks. Open a company to add people to it."
          />
        </li>
      ) : null}
    </ul>
  );
}
