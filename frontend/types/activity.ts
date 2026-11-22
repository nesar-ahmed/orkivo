/**
 * Typed domain contracts for the activity log, mirroring
 * backend/app/modules/activity/schemas.py.
 *
 * Read-only: events are written by the backend in the same transaction as the
 * change they describe, and are never changed afterwards.
 */

export type ActivityVerb =
  | "task.created"
  | "task.updated"
  | "task.deleted"
  | "dependency.added"
  | "dependency.removed"
  | "automation.notified"
  | "comment.added"
  | "comment.edited"
  | "comment.deleted";

/** A person, project or label as it was when the event happened. */
export interface ActivityRef {
  id: string;
  name: string;
}

/**
 * One field's value before and after. `assignee` and `project` hold
 * `ActivityRef`s and `labels` a list of them (`[]` for none); `status`,
 * `priority`, `title`, `due_date` and `description` hold plain values; `null`
 * means "none".
 */
export interface FieldChange {
  from: unknown;
  to: unknown;
}

export type TrackedField =
  | "title"
  | "status"
  | "priority"
  | "assignee"
  | "project"
  | "labels"
  | "due_date"
  | "description";

/** What a `dependency.*` event changed: the task it now waits on, or no longer does. */
export type DependencyField = "blocked_by";

/**
 * What an `automation.notified` event records: who was told (`notified`, a list of
 * `ActivityRef`s) and which rules were on (`rules`, a list of rule names). Its
 * actor is whoever finished the task --- the rule ran because of them.
 */
export type AutomationField = "notified" | "rules";

export interface ActivityPerson {
  id: string;
  display_name: string;
}

export interface ActivityEvent {
  id: string;
  verb: ActivityVerb;
  /** Kept after the task is deleted, so the feed can still name it. */
  task_id: string | null;
  task_title: string | null;
  task_version: number | null;
  comment_id: string | null;
  /** `null` only if the account is gone. */
  actor: ActivityPerson | null;
  changes: Partial<Record<TrackedField | DependencyField | AutomationField, FieldChange>>;
  created_at: string;
}

/** Paginated collection envelope, newest first. */
export interface ActivityListResponse {
  items: ActivityEvent[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
