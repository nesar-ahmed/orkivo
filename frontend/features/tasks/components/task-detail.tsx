"use client";

import { useEffect, useState, useTransition, type FormEvent, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  CalendarDays,
  Eye,
  FolderKanban,
  FolderX,
  Link2,
  Tag,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import { Textarea } from "@/components/ui/textarea";
import { LabelChips } from "@/features/labels/components/label-chip";
import { fetchTask } from "@/features/tasks/api/task-queries";
import { isTaskConflict, updateTask } from "@/features/tasks/api/task-mutations";
import { PriorityIcon, StatusIcon } from "@/features/tasks/components/task-icons";
import { DueChip, UnassignedAvatar } from "@/features/tasks/components/task-meta";
import {
  AssigneePicker,
  LabelPicker,
  PriorityPicker,
  ProjectPicker,
  StatusPicker,
} from "@/features/tasks/components/task-pickers";
import { copyTaskLink } from "@/features/tasks/components/task-row-menu";
import {
  MAX_DUE_DATE,
  MIN_DUE_DATE,
  PRIORITY_LABELS,
  STATUS_LABELS,
  assigneeName,
  formatTimestamp,
  projectName,
  taskCan,
  type TaskChoices,
} from "@/features/tasks/task-utils";
import { useTaskActions, warnIfBlocked } from "@/features/tasks/use-task-actions";
import { ApiError } from "@/lib/api/client";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type {
  Task,
  TaskLabel,
  TaskPerson,
  TaskPriority,
  TaskProject,
  TaskStatus,
  TaskUpdateInput,
} from "@/types/task";

/**
 * The editable fields, as the form holds them (empty string = no value). Labels
 * are the one list: their ids, sorted, so the order they were picked in is never
 * mistaken for a change.
 */
interface Draft {
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string;
  /** A member id, or "" for nobody. */
  assignee_id: string;
  /** A project id, or "" for none. */
  project_id: string;
  /** Label ids, sorted; empty for none. */
  label_ids: readonly string[];
}

type DraftValue = Draft[keyof Draft];

/** Whether two draft values say the same thing; a list compares item by item. */
function sameValue(a: DraftValue, b: DraftValue): boolean {
  if (typeof a === "string" || typeof b === "string") return a === b;
  return a.length === b.length && a.every((item, index) => item === b[index]);
}

function sortedIds(ids: readonly string[]): string[] {
  return [...ids].sort();
}

const FIELD_LABELS: Record<keyof Draft, string> = {
  title: "title",
  description: "description",
  status: "status",
  priority: "priority",
  due_date: "due date",
  assignee_id: "assignee",
  project_id: "project",
  label_ids: "labels",
};

function draftFrom(task: Task): Draft {
  return {
    title: task.title,
    description: task.description ?? "",
    status: task.status,
    priority: task.priority,
    due_date: task.due_date ?? "",
    assignee_id: task.assignee?.id ?? "",
    project_id: task.project?.id ?? "",
    label_ids: sortedIds(task.labels.map((label) => label.id)),
  };
}

/** Only the fields that differ from `base`, in the API's shape. */
function changesBetween(draft: Draft, base: Task): TaskUpdateInput {
  const from = draftFrom(base);
  const changes: TaskUpdateInput = {};
  if (draft.title.trim() !== from.title) changes.title = draft.title.trim();
  if (draft.description.trim() !== from.description.trim()) {
    changes.description = draft.description.trim() || null;
  }
  if (draft.status !== from.status) changes.status = draft.status;
  if (draft.priority !== from.priority) changes.priority = draft.priority;
  if (draft.due_date !== from.due_date) changes.due_date = draft.due_date || null;
  if (draft.assignee_id !== from.assignee_id) changes.assignee_id = draft.assignee_id || null;
  if (draft.project_id !== from.project_id) changes.project_id = draft.project_id || null;
  if (!sameValue(draft.label_ids, from.label_ids)) changes.label_ids = [...draft.label_ids];
  return changes;
}

/**
 * Rebase an edit onto a newer version: keep only the fields this person changed
 * (compared with the version they started from) and take every other field from
 * `latest`. "Keep mine" must never re-send a stale value for a field the colleague
 * changed and this person did not touch.
 */
function rebaseDraft(draft: Draft, startedFrom: Task, latest: Task): Draft {
  const original = draftFrom(startedFrom);
  const next = draftFrom(latest);
  for (const key of Object.keys(FIELD_LABELS) as (keyof Draft)[]) {
    if (!sameValue(draft[key], original[key])) {
      (next as Record<keyof Draft, DraftValue>)[key] = draft[key];
    }
  }
  return next;
}

/** Which fields a colleague changed between two versions of the task. */
function fieldsChanged(before: Task, after: Task): string[] {
  const a = draftFrom(before);
  const b = draftFrom(after);
  return (Object.keys(FIELD_LABELS) as (keyof Draft)[])
    .filter((key) => !sameValue(a[key], b[key]))
    .map((key) => FIELD_LABELS[key]);
}

/**
 * One task, on its own page: read it in full, and edit every field.
 *
 * Shared tasks are edited by several people, so saving sends the version this
 * page loaded. If a colleague saved in between, the API answers 409 and the page
 * shows who changed what, then lets the person choose: take their version, or
 * save their own over it. Nothing is overwritten silently in either direction.
 *
 * Whether it can be edited or deleted comes from the task's own `capabilities`,
 * re-read with every version the page adopts: without `edit` (a viewer, a member
 * looking at someone else's task, or a suspended company) it is shown read-only,
 * and without `delete` there is no delete button.
 *
 * The assignee, project and labels are edited like every other field --- saved
 * with the version, and part of the conflict comparison --- from what `choices`
 * offers. "Keep mine" after a conflict keeps this person's label set only if they
 * changed it; otherwise the colleague's set survives.
 *
 * Deleting is immediate on screen with Undo, like everywhere else: the page goes
 * back to the board and the delete is sent when the Undo window closes.
 */
export function TaskDetail({
  task,
  boardPath,
  shared,
  choices,
}: {
  task: Task;
  boardPath: string;
  shared: boolean;
  choices: TaskChoices;
}) {
  const { assignees } = choices;
  const router = useRouter();
  const actions = useTaskActions();
  const [isPending, startTransition] = useTransition();
  const [base, setBase] = useState<Task>(task);
  const [draft, setDraft] = useState<Draft>(() => draftFrom(task));
  const [seenVersion, setSeenVersion] = useState(task.version);
  const [conflict, setConflict] = useState<{ latest: Task; changed: string[] } | null>(null);
  const [gone, setGone] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const changes = changesBetween(draft, base);
  const dirty = Object.keys(changes).length > 0;
  const canEdit = taskCan(base, "edit");
  const canDelete = taskCan(base, "delete");
  // Everyone the picker can name: the members, plus whoever holds any version on
  // screen, so a person outside the loaded page of members still shows by name.
  const people = knownPeople(assignees.members, [base.assignee, conflict?.latest.assignee]);
  const projects = knownProjects(choices.projects, [base.project, conflict?.latest.project]);
  const labels = knownLabels(choices.labels, [...base.labels, ...(conflict?.latest.labels ?? [])]);

  // A refreshed server render brought a newer version (someone else saved, and
  // this page re-rendered). Adopt it when there is nothing local to lose.
  if (task.version !== seenVersion) {
    setSeenVersion(task.version);
    if (!dirty && task.version > base.version) {
      setBase(task);
      setDraft(draftFrom(task));
    }
  }

  // Warn before leaving with unsaved edits.
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function update<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setNotice(null);
  }

  async function handleFailure(error: unknown, against: Task) {
    if (isTaskConflict(error)) {
      const latest = await fetchTask(against.id).catch(() => null);
      if (latest === null) {
        setGone(true);
        return;
      }
      setConflict({ latest, changed: fieldsChanged(against, latest) });
      return;
    }
    if (error instanceof ApiError && error.status === 404) {
      setGone(true);
      return;
    }
    if (error instanceof ApiError && error.status === 403) {
      // The workspace went into view mode (`WORKSPACE_SUSPENDED`), or the caller's
      // role or this task's holder changed, while this page was open: say why, and
      // re-read what they may do now.
      setGeneralError(error.message);
      router.refresh();
      return;
    }
    const feedback = feedbackFromError(error, "The task could not be saved. Please try again.");
    setFieldErrors(feedback.fieldErrors);
    setGeneralError(feedback.generalError);
  }

  function save(current: Draft = draft, against: Task = base) {
    const pending = changesBetween(current, against);
    if (Object.keys(pending).length === 0) {
      setBase(against);
      setDraft(current);
      setConflict(null);
      return;
    }
    setGeneralError(null);
    setFieldErrors({});
    startTransition(async () => {
      try {
        const saved = await updateTask(against.id, { ...pending, version: against.version });
        if (pending.status) warnIfBlocked(saved, pending.status);
        setBase(saved);
        setDraft(draftFrom(saved));
        setConflict(null);
        setNotice("Saved.");
        router.refresh();
      } catch (error) {
        await handleFailure(error, against);
      }
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (dirty && !isPending) save();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLFormElement>) {
    // Cmd/Ctrl + Enter saves from anywhere in the form, including the description.
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey) && dirty && !isPending) {
      event.preventDefault();
      save();
    }
  }

  function keepMine(latest: Task) {
    // Only my edits go on top of their version; their other changes survive.
    const merged = rebaseDraft(draft, base, latest);
    setBase(latest);
    setDraft(merged);
    save(merged, latest);
  }

  function takeTheirs(latest: Task) {
    setBase(latest);
    setDraft(draftFrom(latest));
    setConflict(null);
    setNotice("Showing the latest version.");
  }

  function handleDelete() {
    actions.remove(base, { afterHide: () => router.push(boardPath) });
  }

  if (gone) {
    return (
      <div role="alert" className="rounded-xl border border-border bg-card p-6 text-sm shadow-sm">
        <p className="font-medium text-card-foreground">This task is no longer available.</p>
        <p className="mt-1 text-muted-foreground">
          It was deleted, or you no longer have access to its workspace.
        </p>
        <ButtonLink href={boardPath} className="mt-4">
          Back to tasks
        </ButtonLink>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      onKeyDown={handleKeyDown}
      aria-label={`Task: ${base.title}`}
      aria-busy={isPending}
      className="flex flex-col gap-5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <ButtonLink href={boardPath} variant="ghost" size="sm" className="-ml-2">
          <ArrowLeft aria-hidden="true" />
          All tasks
        </ButtonLink>
        <div className="ml-auto flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => void copyTaskLink(window.location.pathname)}
          >
            <Link2 aria-hidden="true" />
            Copy link
          </Button>
          {canDelete ? (
            <Button
              type="button"
              variant="danger"
              size="sm"
              onClick={handleDelete}
              disabled={isPending}
            >
              <Trash2 aria-hidden="true" />
              Delete task
            </Button>
          ) : null}
        </div>
      </div>

      {conflict ? (
        <div
          role="alert"
          className="flex gap-3 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning"
        >
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">
              {conflict.latest.updated_by?.display_name ?? "Someone"} changed this task after you
              opened it.
            </p>
            <p className="mt-1 text-xs">
              {conflict.changed.length > 0
                ? `They changed the ${conflict.changed.join(", ")}. `
                : ""}
              Choose which version to keep. Nothing has been overwritten.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => takeTheirs(conflict.latest)}
              >
                Use their version
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => keepMine(conflict.latest)}
                disabled={isPending}
              >
                Save mine over theirs
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <section className="flex min-w-0 flex-col gap-3">
          {canEdit ? (
            <>
              <div>
                <label htmlFor="task-detail-title" className="sr-only">
                  Title
                </label>
                <Input
                  id="task-detail-title"
                  value={draft.title}
                  required
                  maxLength={200}
                  onChange={(event) => update("title", event.target.value)}
                  aria-invalid={Boolean(fieldErrors.title)}
                  className="h-auto border-transparent bg-transparent px-2 py-1.5 text-2xl font-semibold tracking-tight shadow-none hover:border-border focus-visible:bg-card"
                  disabled={isPending}
                />
                {fieldErrors.title ? (
                  <p role="alert" className="mt-1 px-2 text-xs text-danger">
                    {fieldErrors.title}
                  </p>
                ) : null}
              </div>
              <div>
                <label htmlFor="task-detail-description" className="sr-only">
                  Description
                </label>
                <Textarea
                  id="task-detail-description"
                  value={draft.description}
                  rows={12}
                  maxLength={5000}
                  placeholder="Add details, links or acceptance criteria…"
                  onChange={(event) => update("description", event.target.value)}
                  aria-invalid={Boolean(fieldErrors.description)}
                  className="border-transparent bg-transparent px-2 text-[0.95rem] leading-relaxed shadow-none hover:border-border focus-visible:bg-card"
                  disabled={isPending}
                />
                {fieldErrors.description ? (
                  <p role="alert" className="mt-1 px-2 text-xs text-danger">
                    {fieldErrors.description}
                  </p>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <h2 className="px-2 text-2xl font-semibold tracking-tight text-foreground">
                {base.title}
              </h2>
              {base.description ? (
                <p className="px-2 text-[0.95rem] leading-relaxed whitespace-pre-wrap text-foreground">
                  {base.description}
                </p>
              ) : (
                <p className="px-2 text-sm text-muted-foreground">No description.</p>
              )}
            </>
          )}
        </section>

        <aside className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 shadow-xs lg:self-start">
          <Property label="Status">
            {canEdit ? (
              <StatusPicker
                look="field"
                value={draft.status}
                onChange={(status: TaskStatus) => update("status", status)}
                disabled={isPending}
              />
            ) : (
              <span className="flex items-center gap-2 text-sm">
                <StatusIcon status={base.status} />
                {STATUS_LABELS[base.status]}
              </span>
            )}
          </Property>
          <Property label="Priority">
            {canEdit ? (
              <PriorityPicker
                look="field"
                value={draft.priority}
                onChange={(priority: TaskPriority) => update("priority", priority)}
                disabled={isPending}
              />
            ) : (
              <span className="flex items-center gap-2 text-sm">
                <PriorityIcon priority={base.priority} />
                {PRIORITY_LABELS[base.priority]}
              </span>
            )}
          </Property>
          <Property label="Assignee">
            {canEdit ? (
              <AssigneePicker
                look="field"
                value={draft.assignee_id}
                people={people}
                viewerId={assignees.viewerId}
                onChange={(assigneeId) => update("assignee_id", assigneeId)}
                disabled={isPending}
              />
            ) : (
              <span className="flex items-center gap-2 text-sm">
                {base.assignee ? (
                  <Avatar name={base.assignee.display_name} seed={base.assignee.id} size="xs" />
                ) : (
                  <UnassignedAvatar size="xs" />
                )}
                {assigneeName(base.assignee, assignees.viewerId)}
              </span>
            )}
            {fieldErrors.assignee_id ? (
              <p role="alert" className="mt-1 text-xs text-danger">
                {fieldErrors.assignee_id}
              </p>
            ) : null}
          </Property>
          <Property label="Project">
            {canEdit ? (
              <ProjectPicker
                look="field"
                value={draft.project_id}
                projects={projects}
                onChange={(projectId) => update("project_id", projectId)}
                disabled={isPending}
              />
            ) : (
              <span className="flex items-center gap-2 text-sm">
                {base.project ? (
                  <FolderKanban aria-hidden="true" className="size-4 text-muted-foreground" />
                ) : (
                  <FolderX aria-hidden="true" className="size-4 text-muted-foreground" />
                )}
                {projectName(base.project)}
              </span>
            )}
            {fieldErrors.project_id ? (
              <p role="alert" className="mt-1 text-xs text-danger">
                {fieldErrors.project_id}
              </p>
            ) : null}
          </Property>
          <Property label="Labels" htmlFor={canEdit ? "task-detail-labels" : undefined}>
            {canEdit ? (
              <LabelPicker
                id="task-detail-labels"
                value={draft.label_ids}
                labels={labels}
                onChange={(ids) => update("label_ids", sortedIds(ids))}
                disabled={isPending}
              />
            ) : base.labels.length > 0 ? (
              <LabelChips labels={base.labels} max={base.labels.length} />
            ) : (
              <span className="flex items-center gap-2 text-sm text-muted-foreground">
                <Tag aria-hidden="true" className="size-4" />
                No labels
              </span>
            )}
            {fieldErrors.label_ids ? (
              <p role="alert" className="mt-1 text-xs text-danger">
                {fieldErrors.label_ids}
              </p>
            ) : null}
          </Property>
          <Property label="Due date" htmlFor={canEdit ? "task-detail-due" : undefined}>
            {canEdit ? (
              <>
                <Input
                  id="task-detail-due"
                  type="date"
                  min={MIN_DUE_DATE}
                  max={MAX_DUE_DATE}
                  value={draft.due_date}
                  onChange={(event) => update("due_date", event.target.value)}
                  aria-invalid={Boolean(fieldErrors.due_date)}
                  disabled={isPending}
                />
                {fieldErrors.due_date ? (
                  <p role="alert" className="mt-1 text-xs text-danger">
                    {fieldErrors.due_date}
                  </p>
                ) : null}
              </>
            ) : base.due_date ? (
              <DueChip task={base} />
            ) : (
              <span className="flex items-center gap-2 text-sm text-muted-foreground">
                <CalendarDays aria-hidden="true" className="size-4" />
                No due date
              </span>
            )}
          </Property>

          <dl className="flex flex-col gap-3 border-t border-border pt-4 text-xs">
            <div className="flex items-center gap-2">
              <dt className="w-20 shrink-0 text-muted-foreground">Visibility</dt>
              <dd className="flex items-center gap-1.5 font-medium text-foreground">
                <Eye aria-hidden="true" className="size-3.5 text-muted-foreground" />
                {shared ? "Everyone in this company" : "Only you"}
              </dd>
            </div>
            <div className="flex items-start gap-2">
              <dt className="w-20 shrink-0 pt-1 text-muted-foreground">Created</dt>
              <dd className="flex min-w-0 items-start gap-2 text-foreground">
                <Avatar
                  name={base.created_by?.display_name ?? "?"}
                  seed={base.created_by?.id}
                  size="sm"
                />
                <span className="min-w-0">
                  <span className="block truncate font-medium">
                    {base.created_by?.display_name ?? "A former member"}
                  </span>
                  <span className="block text-muted-foreground">
                    {formatTimestamp(base.created_at)}
                  </span>
                </span>
              </dd>
            </div>
            {base.updated_by ? (
              <div className="flex items-start gap-2">
                <dt className="w-20 shrink-0 pt-1 text-muted-foreground">Last edited</dt>
                <dd className="flex min-w-0 items-start gap-2 text-foreground">
                  <Avatar name={base.updated_by.display_name} seed={base.updated_by.id} size="sm" />
                  <span className="min-w-0">
                    <span className="block truncate font-medium">
                      {base.updated_by.display_name}
                    </span>
                    <span className="block text-muted-foreground">
                      {formatTimestamp(base.updated_at)}
                    </span>
                  </span>
                </dd>
              </div>
            ) : null}
          </dl>
        </aside>
      </div>

      {generalError ? (
        <p
          role="alert"
          className="rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        >
          {generalError}
        </p>
      ) : null}

      <p aria-live="polite" className={notice ? "px-2 text-xs text-muted-foreground" : "sr-only"}>
        {notice ?? ""}
      </p>

      {canEdit && dirty ? (
        <div className="sticky bottom-4 z-10 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-popover/95 p-3 shadow-lg backdrop-blur animate-pop-in">
          <p className="text-sm font-medium text-popover-foreground">Unsaved changes</p>
          <p className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
            <Kbd>Ctrl</Kbd>+<Kbd>Enter</Kbd> to save
          </p>
          <div className="ml-auto flex gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setDraft(draftFrom(base));
                setFieldErrors({});
                setGeneralError(null);
              }}
              disabled={isPending}
            >
              Discard
            </Button>
            <Button type="submit" size="sm" disabled={isPending || draft.title.trim().length === 0}>
              {isPending ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </div>
      ) : null}
    </form>
  );
}

/** Members first, then anyone else named, each once. */
function knownPeople(
  members: readonly TaskPerson[],
  extra: readonly (TaskPerson | null | undefined)[],
): TaskPerson[] {
  const seen = new Set(members.map((member) => member.id));
  const people = [...members];
  for (const person of extra) {
    if (person && !seen.has(person.id)) {
      seen.add(person.id);
      people.push(person);
    }
  }
  return people;
}

/** The workspace's projects first, then any other project named, each once. */
function knownProjects(
  projects: readonly TaskProject[],
  extra: readonly (TaskProject | null | undefined)[],
): TaskProject[] {
  const seen = new Set(projects.map((project) => project.id));
  const known = [...projects];
  for (const project of extra) {
    if (project && !seen.has(project.id)) {
      seen.add(project.id);
      known.push(project);
    }
  }
  return known;
}

/** The workspace's labels first, then any other label named, each once. */
function knownLabels(
  labels: readonly TaskLabel[],
  extra: readonly TaskLabel[],
): TaskLabel[] {
  const seen = new Set(labels.map((label) => label.id));
  const known = [...labels];
  for (const label of extra) {
    if (!seen.has(label.id)) {
      seen.add(label.id);
      known.push(label);
    }
  }
  return known;
}

/** One labelled property in the task's side panel. */
function Property({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      {htmlFor ? (
        <label htmlFor={htmlFor} className="mb-1.5 block text-xs font-medium text-muted-foreground">
          {label}
        </label>
      ) : (
        <p className="mb-1.5 text-xs font-medium text-muted-foreground">{label}</p>
      )}
      {children}
    </div>
  );
}
