import Link from "next/link";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  LOAD_ROW,
  LoadBar,
  LoadLegend,
  LoadNumbers,
} from "@/features/insights/components/load-bar";
import { UnassignedAvatar } from "@/features/tasks/components/task-meta";
import {
  WORKSPACE_ROLE_BADGES,
  WORKSPACE_ROLE_LABELS,
} from "@/features/workspaces/workspace-utils";
import type { MemberWorkload } from "@/types/insights";

/**
 * How open work is spread across a company: one row per person, busiest first
 * (the API's order), each opening that person's open tasks.
 *
 * The shape every team tool converges on --- Jira's team workload, Asana's and
 * ClickUp's workload views --- because it answers the two questions a lead asks:
 * who is overloaded, and who has room. Overdue work is called out per person.
 * People with nothing open are folded into one line underneath rather than
 * drawn as empty bars, so a large company's busy people are never pushed off the
 * card; unassigned work is its own row, since nobody is on it.
 */
export function WorkloadList({
  workload,
  viewerId,
  hrefFor,
}: {
  workload: readonly MemberWorkload[];
  viewerId: string | null;
  /** A member's id, or `none` for the unassigned row. */
  hrefFor: (assignee: string) => string;
}) {
  const busy = workload.filter((row) => row.person !== null && row.counts.open > 0);
  const idle = workload.filter((row) => row.person !== null && row.counts.open === 0);
  const unassigned = workload.find((row) => row.person === null && row.counts.open > 0);
  const busiest = Math.max(1, ...workload.map((row) => row.counts.open));

  if (busy.length === 0 && !unassigned) {
    return (
      <p className="text-sm text-muted-foreground">
        Nobody has open work right now. New tasks and assignments will show up here.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <LoadLegend />
      <ul className="flex flex-col">
        {busy.map((row) => {
          const person = row.person!;
          return (
            <li key={person.id}>
              <Link
                href={hrefFor(person.id)}
                className={LOAD_ROW}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <Avatar name={person.display_name} seed={person.id} size="sm" />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-card-foreground">
                      {person.display_name}
                      {person.id === viewerId ? (
                        <span className="ml-1 text-xs font-normal text-muted-foreground">(you)</span>
                      ) : null}
                    </span>
                    {row.role ? (
                      <Badge variant={WORKSPACE_ROLE_BADGES[row.role]} className="mt-0.5">
                        {WORKSPACE_ROLE_LABELS[row.role]}
                      </Badge>
                    ) : null}
                  </span>
                </span>
                <LoadBar counts={row.counts} busiest={busiest} />
                <LoadNumbers counts={row.counts} />
              </Link>
            </li>
          );
        })}
        {unassigned ? (
          <li>
            <Link
              href={hrefFor("none")}
              className={LOAD_ROW}
            >
              <span className="flex min-w-0 items-center gap-2">
                <UnassignedAvatar />
                <span className="truncate text-sm font-medium text-muted-foreground">
                  Unassigned
                </span>
              </span>
              <LoadBar counts={unassigned.counts} busiest={busiest} />
              <LoadNumbers counts={unassigned.counts} />
            </Link>
          </li>
        ) : null}
      </ul>
      {idle.length > 0 ? (
        <details className="group text-xs text-muted-foreground">
          <summary className="cursor-pointer rounded-md py-1 select-none hover:text-foreground">
            {idle.length} {idle.length === 1 ? "person has" : "people have"} nothing open
          </summary>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {idle.map((row) => (
              <li
                key={row.person!.id}
                className="flex items-center gap-1.5 rounded-full border border-border py-0.5 pr-2 pl-0.5"
              >
                <Avatar name={row.person!.display_name} seed={row.person!.id} size="xs" />
                <span className="text-card-foreground">{row.person!.display_name}</span>
                {row.role ? <span>· {WORKSPACE_ROLE_LABELS[row.role]}</span> : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
