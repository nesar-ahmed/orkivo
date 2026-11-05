"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Columns3, List, ListFilter, Plus, Search, X } from "lucide-react";
import { Button, buttonClasses } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PriorityIcon, StatusIcon } from "@/features/tasks/components/task-icons";
import { NewTaskDialog } from "@/features/tasks/components/new-task-dialog";
import { isFiltered, taskQueryHref, type TaskQuery } from "@/features/tasks/task-query";
import { PRIORITY_LABELS, STATUS_LABELS, STATUS_ORDER } from "@/features/tasks/task-utils";
import { cn } from "@/lib/utils/cn";
import type { TaskPriority, TaskStatus } from "@/types/task";

const ANY = "any";
const SEARCH_DEBOUNCE_MS = 300;

/**
 * View switch, search and filters for a board. Everything is written to the URL
 * (`?view=board&priority=high&search=…`), so a filtered view can be shared and
 * survives a reload. Search is debounced and *replaces* the history entry, so
 * typing does not fill the back button; filters and views *push*, so Back undoes
 * them.
 */
export function TaskToolbar({
  basePath,
  query,
  canEdit,
  workspaceId,
  shared,
}: {
  basePath: string;
  query: TaskQuery;
  canEdit: boolean;
  workspaceId: string;
  shared: boolean;
}) {
  const router = useRouter();
  const [search, setSearch] = useState(query.search ?? "");
  const [syncedSearch, setSyncedSearch] = useState(query.search);

  // The URL changed from elsewhere (Back, a link): show its search term.
  if (query.search !== syncedSearch) {
    setSyncedSearch(query.search);
    if ((search.trim() || undefined) !== query.search) setSearch(query.search ?? "");
  }

  useEffect(() => {
    const next = search.trim() || undefined;
    if (next === query.search) return;
    const timer = window.setTimeout(() => {
      router.replace(taskQueryHref(basePath, query, { search: next }), { scroll: false });
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [search, query, basePath, router]);

  const go = (changes: Partial<TaskQuery>) =>
    router.push(taskQueryHref(basePath, query, changes), { scroll: false });

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div
        role="group"
        aria-label="View"
        className="inline-flex rounded-lg border border-border bg-muted/60 p-0.5"
      >
        <ViewLink
          href={taskQueryHref(basePath, query, { view: "list" })}
          active={query.view === "list"}
          icon={<List aria-hidden="true" />}
          label="List"
        />
        <ViewLink
          href={taskQueryHref(basePath, query, { view: "board" })}
          active={query.view === "board"}
          icon={<Columns3 aria-hidden="true" />}
          label="Board"
        />
      </div>

      <div className="relative min-w-40 flex-1 sm:max-w-64">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <label htmlFor="task-search" className="sr-only">
          Search tasks
        </label>
        <input
          id="task-search"
          type="search"
          value={search}
          maxLength={200}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search tasks…"
          className={cn(
            "h-8 w-full rounded-md border border-border bg-card pr-2 pl-8 text-sm shadow-xs",
            "placeholder:text-muted-foreground hover:border-border-strong focus-visible:border-primary",
            "focus-visible:ring-3 focus-visible:ring-primary/20 focus-visible:outline-none",
          )}
        />
      </div>

      {query.view === "list" ? (
        <FilterMenu<TaskStatus>
          label="Status"
          value={query.status}
          options={STATUS_ORDER}
          labels={STATUS_LABELS}
          icon={(value) => <StatusIcon status={value} />}
          onChange={(status) => go({ status })}
        />
      ) : null}
      <FilterMenu<TaskPriority>
        label="Priority"
        value={query.priority}
        options={["high", "medium", "low"]}
        labels={PRIORITY_LABELS}
        icon={(value) => <PriorityIcon priority={value} />}
        onChange={(priority) => go({ priority })}
      />

      {isFiltered(query) ? (
        <Link
          href={taskQueryHref(basePath, query, {
            search: undefined,
            status: undefined,
            priority: undefined,
          })}
          onClick={() => setSearch("")}
          className={buttonClasses("ghost", "sm")}
        >
          <X aria-hidden="true" />
          Clear filters
        </Link>
      ) : null}

      {canEdit ? (
        <div className="ml-auto">
          <NewTaskDialog
            workspaceId={workspaceId}
            shared={shared}
            basePath={basePath}
            trigger={
              <Button size="sm">
                <Plus aria-hidden="true" />
                New task
              </Button>
            }
          />
        </div>
      ) : null}
    </div>
  );
}

function ViewLink({
  href,
  active,
  icon,
  label,
}: {
  href: string;
  active: boolean;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium transition-colors [&_svg]:size-4",
        active
          ? "bg-card text-foreground shadow-xs ring-1 ring-border"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {icon}
      {label}
    </Link>
  );
}

function FilterMenu<T extends string>({
  label,
  value,
  options,
  labels,
  icon,
  onChange,
}: {
  label: string;
  value: T | undefined;
  options: readonly T[];
  labels: Record<T, string>;
  icon: (value: T) => React.ReactNode;
  onChange: (value: T | undefined) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          buttonClasses("secondary", "sm"),
          value && "border-primary/40 bg-primary/5 text-primary hover:bg-primary/10",
        )}
      >
        {value ? icon(value) : <ListFilter aria-hidden="true" />}
        {value ? `${label}: ${labels[value]}` : label}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-48">
        <DropdownMenuLabel>Filter by {label.toLowerCase()}</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={value ?? ANY}
          onValueChange={(next) => onChange(next === ANY ? undefined : (next as T))}
        >
          <DropdownMenuRadioItem value={ANY}>Any {label.toLowerCase()}</DropdownMenuRadioItem>
          {options.map((option) => (
            <DropdownMenuRadioItem key={option} value={option}>
              {icon(option)}
              {labels[option]}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
