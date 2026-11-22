"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CalendarClock,
  CalendarDays,
  CalendarX,
  CircleDashed,
  Columns3,
  FolderKanban,
  FolderX,
  List,
  Plus,
  Rows3,
  Tag,
  TagX,
  UserRound,
  X,
} from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { Button, buttonClasses } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LabelDot } from "@/features/labels/components/label-chip";
import { PriorityIcon, StatusIcon } from "@/features/tasks/components/task-icons";
import { NewTaskDialog } from "@/features/tasks/components/new-task-dialog";
import { UnassignedAvatar } from "@/features/tasks/components/task-meta";
import {
  FilterMenu,
  SearchBox,
  ViewSwitch,
} from "@/features/tasks/components/toolbar-controls";
import {
  DUE_FILTERS,
  DUE_FILTER_LABELS,
  type DueFilter,
} from "@/features/tasks/task-dates";
import {
  NO_FILTERS,
  isFiltered,
  taskQueryHref,
  type TaskGrouping,
  type TaskQuery,
} from "@/features/tasks/task-query";
import {
  PRIORITY_LABELS,
  STATUS_FILTERS,
  STATUS_FILTER_LABELS,
  assigneeName,
  type AssigneeOptions,
  type TaskChoices,
  type TaskDefaults,
} from "@/features/tasks/task-utils";
import { cn } from "@/lib/utils/cn";
import type {
  TaskAssigneeFilter,
  TaskLabel,
  TaskLabelFilter,
  TaskPriority,
  TaskProject,
  TaskProjectFilter,
  TaskStatusFilter,
} from "@/types/task";

/** A status filter's icon: the status's own, or a dashed ring for "open". */
export function statusFilterIcon(value: TaskStatusFilter) {
  return value === "open" ? (
    <CircleDashed aria-hidden="true" />
  ) : (
    <StatusIcon status={value} />
  );
}

/**
 * View switch, grouping, search and filters for a board. Everything is written
 * to the URL (`?view=board&group=project&assignee=me&label=…&search=…`), so a
 * filtered view can be shared and survives a reload. Search is debounced and
 * *replaces* the history entry, so typing does not fill the back button; filters,
 * grouping and views *push*, so Back undoes them.
 *
 * The board splits by status already, so only the list and the calendar offer a
 * status filter; grouping by project is for the list and the board.
 */
export function TaskToolbar({
  basePath,
  query,
  canCreate,
  workspaceId,
  shared,
  choices,
  defaults,
}: {
  basePath: string;
  query: TaskQuery;
  /** Whether "New task" is offered: the workspace's `edit_content`. */
  canCreate: boolean;
  workspaceId: string;
  shared: boolean;
  choices: TaskChoices;
  defaults: TaskDefaults;
}) {
  const router = useRouter();
  const go = (changes: Partial<TaskQuery>) =>
    router.push(taskQueryHref(basePath, query, changes), { scroll: false });

  return (
    <div className="flex flex-wrap items-center gap-2">
      <ViewSwitch
        options={[
          {
            href: taskQueryHref(basePath, query, { view: "list" }),
            active: query.view === "list",
            icon: <List aria-hidden="true" />,
            label: "List",
          },
          {
            href: taskQueryHref(basePath, query, { view: "board" }),
            active: query.view === "board",
            icon: <Columns3 aria-hidden="true" />,
            label: "Board",
          },
          {
            href: taskQueryHref(basePath, query, { view: "calendar" }),
            active: query.view === "calendar",
            icon: <CalendarDays aria-hidden="true" />,
            label: "Calendar",
          },
        ]}
      />
      {query.view !== "calendar" ? (
        <GroupMenu value={query.group} onChange={(group) => go({ group })} />
      ) : null}

      <SearchBox
        id="task-search"
        value={query.search}
        hrefFor={(search) => taskQueryHref(basePath, query, { search })}
      />

      {query.view !== "board" ? (
        <FilterMenu<TaskStatusFilter>
          label="Status"
          value={query.status}
          options={STATUS_FILTERS}
          labels={STATUS_FILTER_LABELS}
          icon={statusFilterIcon}
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
      <AssigneeFilter
        value={query.assignee}
        assignees={choices.assignees}
        onChange={(assignee) => go({ assignee })}
      />
      <ProjectFilter
        value={query.project}
        projects={choices.projects}
        onChange={(project) => go({ project })}
      />
      <LabelFilter
        value={query.label}
        labels={choices.labels}
        onChange={(label) => go({ label })}
      />
      {query.view !== "calendar" ? (
        <FilterMenu<DueFilter>
          label="Due"
          value={query.due}
          options={DUE_FILTERS}
          labels={DUE_FILTER_LABELS}
          icon={(value) =>
            value === "none" ? <CalendarX aria-hidden="true" /> : <CalendarClock aria-hidden="true" />
          }
          onChange={(due) => go({ due })}
          anyLabel="Any due date"
        />
      ) : null}

      {isFiltered(query) ? (
        <Link
          href={taskQueryHref(basePath, query, NO_FILTERS)}
          className={buttonClasses("ghost", "sm")}
        >
          <X aria-hidden="true" />
          Clear filters
        </Link>
      ) : null}

      {canCreate ? (
        <div className="ml-auto">
          <NewTaskDialog
            workspaceId={workspaceId}
            shared={shared}
            basePath={basePath}
            choices={choices}
            defaults={defaults}
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

/**
 * Whose tasks to show: the viewer's, nobody's, or one member's. `me` stays `me`
 * in the URL rather than becoming the viewer's id, so a link to "my tasks" shows
 * whoever opens it their own.
 */
function AssigneeFilter({
  value,
  assignees,
  onChange,
}: {
  value: TaskAssigneeFilter | undefined;
  assignees: AssigneeOptions;
  onChange: (value: TaskAssigneeFilter | undefined) => void;
}) {
  const { members, viewerId } = assignees;
  const viewer = members.find((member) => member.id === viewerId);
  const others = members.filter((member) => member.id !== viewerId);
  const byId = new Map(members.map((member) => [member.id, member]));

  const options: TaskAssigneeFilter[] = ["me", "none", ...others.map((member) => member.id)];
  const labels: Record<string, string> = { me: "Me", none: "Unassigned" };
  for (const member of members) labels[member.id] = assigneeName(member, viewerId);
  // A filter link can name someone who has since left: say so rather than show an id.
  if (value && !(value in labels)) labels[value] = "A former member";

  return (
    <FilterMenu<TaskAssigneeFilter>
      label="Assignee"
      value={value}
      options={options}
      labels={labels}
      icon={(option) => {
        const person = option === "me" ? viewer : byId.get(option);
        if (person) return <Avatar name={person.display_name} seed={person.id} size="xs" />;
        if (option === "me") return <UserRound aria-hidden="true" />;
        return <UnassignedAvatar size="xs" />;
      }}
      onChange={onChange}
      contentClassName="max-h-80 w-56 overflow-y-auto"
    />
  );
}

/**
 * Which tasks to show by project: one project's, or those outside every project.
 * Hidden while the workspace has no projects, unless a link already filters by
 * one (which then reads as a deleted project rather than an id).
 */
function ProjectFilter({
  value,
  projects,
  onChange,
}: {
  value: TaskProjectFilter | undefined;
  projects: readonly TaskProject[];
  onChange: (value: TaskProjectFilter | undefined) => void;
}) {
  if (projects.length === 0 && !value) return null;
  const options: TaskProjectFilter[] = ["none", ...projects.map((project) => project.id)];
  const labels: Record<string, string> = { none: "No project" };
  for (const project of projects) labels[project.id] = project.name;
  if (value && !(value in labels)) labels[value] = "A deleted project";

  return (
    <FilterMenu<TaskProjectFilter>
      label="Project"
      value={value}
      options={options}
      labels={labels}
      icon={(option) =>
        option === "none" ? <FolderX aria-hidden="true" /> : <FolderKanban aria-hidden="true" />
      }
      onChange={onChange}
      contentClassName="max-h-80 w-56 overflow-y-auto"
    />
  );
}

/**
 * Which tasks to show by label: those carrying one label, or those carrying none.
 * Hidden while the workspace has no labels, unless a link already filters by one
 * (which then reads as a deleted label rather than an id).
 */
function LabelFilter({
  value,
  labels,
  onChange,
}: {
  value: TaskLabelFilter | undefined;
  labels: readonly TaskLabel[];
  onChange: (value: TaskLabelFilter | undefined) => void;
}) {
  if (labels.length === 0 && !value) return null;
  const byId = new Map(labels.map((label) => [label.id, label]));
  const options: TaskLabelFilter[] = ["none", ...byId.keys()];
  const names: Record<string, string> = { none: "No labels" };
  for (const label of labels) names[label.id] = label.name;
  if (value && !(value in names)) names[value] = "A deleted label";

  return (
    <FilterMenu<TaskLabelFilter>
      label="Label"
      value={value}
      options={options}
      labels={names}
      icon={(option) => {
        if (option === "none") return <TagX aria-hidden="true" />;
        const label = byId.get(option);
        return label ? <LabelDot color={label.color} /> : <Tag aria-hidden="true" />;
      }}
      onChange={onChange}
      contentClassName="max-h-80 w-56 overflow-y-auto"
    />
  );
}

const NO_GROUPING = "none";

/**
 * Split the view into sections (list) or swimlanes (board) by project. Not a
 * filter --- every task stays visible --- so "Clear filters" leaves it alone.
 */
function GroupMenu({
  value,
  onChange,
}: {
  value: TaskGrouping | undefined;
  onChange: (value: TaskGrouping | undefined) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          buttonClasses("secondary", "sm"),
          value && "border-primary/40 bg-primary/5 text-primary hover:bg-primary/10",
        )}
      >
        <Rows3 aria-hidden="true" />
        {value ? "Group: Project" : "Group"}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-48">
        <DropdownMenuLabel>Group tasks</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={value ?? NO_GROUPING}
          onValueChange={(next) =>
            onChange(next === NO_GROUPING ? undefined : (next as TaskGrouping))
          }
        >
          <DropdownMenuRadioItem value={NO_GROUPING}>No grouping</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="project">
            <FolderKanban aria-hidden="true" />
            By project
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
