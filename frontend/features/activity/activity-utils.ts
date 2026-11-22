/**
 * Turning an activity event into a sentence.
 *
 * One function serves both places events are read: a task's own timeline, where
 * the task is "this task" and "it", and a workspace's feed, where it is named.
 * Values are the ones recorded at the time --- names of people, projects and
 * labels are snapshots --- so an old event reads the same after a rename or a
 * deletion.
 */

import { PRIORITY_LABELS, STATUS_LABELS, formatDueDate } from "@/features/tasks/task-utils";
import type { ActivityEvent, ActivityRef, FieldChange, TrackedField } from "@/types/activity";
import type { TaskPriority, TaskStatus } from "@/types/task";

/** The order a reader expects when one save changed several things. */
const FIELD_ORDER: readonly TrackedField[] = [
  "title",
  "status",
  "priority",
  "assignee",
  "project",
  "labels",
  "due_date",
  "description",
];

function ref(value: unknown): ActivityRef | null {
  return value && typeof value === "object" && "name" in value ? (value as ActivityRef) : null;
}

/** A recorded list of labels; anything else (an older shape, say) reads as none. */
function refs(value: unknown): ActivityRef[] {
  return Array.isArray(value) ? value.map(ref).filter((item) => item !== null) : [];
}

/** "A", "A and B", "A, B and C". */
function listNames(items: readonly ActivityRef[]): string {
  const names = items.map((item) => item.name);
  if (names.length <= 1) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

function labelNoun(items: readonly ActivityRef[]): string {
  return items.length === 1 ? "label" : "labels";
}

function quoted(value: unknown): string {
  return `“${String(value ?? "")}”`;
}

function statusLabel(value: unknown): string {
  return STATUS_LABELS[value as TaskStatus] ?? String(value);
}

function priorityLabel(value: unknown): string {
  return PRIORITY_LABELS[value as TaskPriority] ?? String(value);
}

/**
 * One clause per changed field. `it` names the task in the first clause only;
 * `actorId` lets "assigned it to Sam", written by Sam, read "to themselves".
 */
function fieldClause(
  field: TrackedField,
  change: FieldChange,
  it: string,
  actorId: string | undefined,
): string {
  const who = (person: ActivityRef) => (person.id === actorId ? "themselves" : person.name);
  const { from, to } = change;
  switch (field) {
    case "title":
      return `renamed ${from === null ? it : quoted(from)} to ${quoted(to)}`;
    case "status":
      return from === null
        ? `set the status of ${it} to ${statusLabel(to)}`
        : `moved ${it} from ${statusLabel(from)} to ${statusLabel(to)}`;
    case "priority":
      return from === null
        ? `set the priority of ${it} to ${priorityLabel(to)}`
        : `changed the priority of ${it} from ${priorityLabel(from)} to ${priorityLabel(to)}`;
    case "assignee": {
      const before = ref(from);
      const after = ref(to);
      if (!after) return `unassigned ${before ? who(before) : "someone"} from ${it}`;
      if (!before) return `assigned ${it} to ${who(after)}`;
      return `reassigned ${it} from ${who(before)} to ${who(after)}`;
    }
    case "project": {
      const before = ref(from);
      const after = ref(to);
      if (!after) return `removed ${it} from ${before?.name ?? "its project"}`;
      if (!before) return `added ${it} to ${after.name}`;
      return `moved ${it} from ${before.name} to ${after.name}`;
    }
    case "labels": {
      const before = refs(from);
      const after = refs(to);
      const added = after.filter((label) => !before.some((old) => old.id === label.id));
      const removed = before.filter((label) => !after.some((now) => now.id === label.id));
      if (added.length > 0 && removed.length > 0) {
        const gone = `the ${listNames(removed)} ${labelNoun(removed)}`;
        return `labelled ${it} ${listNames(added)} and removed ${gone}`;
      }
      if (added.length > 0) return `labelled ${it} ${listNames(added)}`;
      if (removed.length > 0) {
        return `removed the ${listNames(removed)} ${labelNoun(removed)} from ${it}`;
      }
      return `changed the labels of ${it}`;
    }
    case "due_date":
      return to
        ? `set the due date of ${it} to ${formatDueDate(String(to))}`
        : `cleared the due date of ${it}`;
    case "description":
      return `edited the description of ${it}`;
  }
}

function joinClauses(clauses: string[]): string {
  if (clauses.length <= 1) return clauses[0] ?? "";
  return `${clauses.slice(0, -1).join(", ")} and ${clauses[clauses.length - 1]}`;
}

/**
 * What the actor did, as the rest of a sentence that starts with their name:
 * "moved it from To do to Done and assigned it to Mo".
 *
 * `inTask`: the reader is on the task's own page, so the task is "this task" /
 * "it" rather than its title.
 */
export function describeActivity(event: ActivityEvent, { inTask }: { inTask: boolean }): string {
  const named = inTask ? "this task" : quoted(event.task_title ?? "a task");
  const on = inTask ? "" : ` on ${named}`;
  switch (event.verb) {
    case "task.created": {
      const extras = [
        ref(event.changes.project?.to) ? `in ${ref(event.changes.project?.to)?.name}` : null,
        ref(event.changes.assignee?.to)
          ? `assigned to ${
              ref(event.changes.assignee?.to)?.id === event.actor?.id
                ? "themselves"
                : ref(event.changes.assignee?.to)?.name
            }`
          : null,
        refs(event.changes.labels?.to).length > 0
          ? `labelled ${listNames(refs(event.changes.labels?.to))}`
          : null,
      ].filter(Boolean);
      return [`created ${named}`, ...extras].join(", ");
    }
    case "task.deleted":
      return `deleted ${named}`;
    case "dependency.added": {
      const blocker = ref(event.changes.blocked_by?.to);
      return `marked ${named} as blocked by ${quoted(blocker?.name ?? "a task")}`;
    }
    case "dependency.removed": {
      const blocker = ref(event.changes.blocked_by?.from);
      return `marked ${named} as no longer blocked by ${quoted(blocker?.name ?? "a task")}`;
    }
    case "automation.notified": {
      const told = listNames(refs(event.changes.notified?.to)) || "people";
      const finisher = event.actor?.display_name ?? "a former member";
      return `notified ${told} that ${named} was completed by ${finisher}`;
    }
    case "comment.added":
      return `commented${on}`;
    case "comment.edited":
      return `edited a comment${on}`;
    case "comment.deleted":
      return `deleted a comment${on}`;
    case "task.updated": {
      const fields = FIELD_ORDER.filter((field) => event.changes[field]);
      if (fields.length === 0) return `updated ${named}`;
      return joinClauses(
        fields.map((field, index) =>
          fieldClause(
            field,
            event.changes[field]!,
            index === 0 ? (inTask ? "it" : named) : "it",
            event.actor?.id,
          ),
        ),
      );
    }
  }
}

/**
 * Whether a workspace automation, rather than a person, did what the event says.
 * Such events are shown with "Automation" as their subject; the person whose
 * change set it off is named in the sentence.
 */
export function isAutomated(event: ActivityEvent): boolean {
  return event.verb.startsWith("automation.");
}

/** Whether an event is one a comment card already shows on a task's timeline. */
export function isShownAsComment(event: ActivityEvent): boolean {
  return event.verb === "comment.added" || event.verb === "comment.edited";
}
