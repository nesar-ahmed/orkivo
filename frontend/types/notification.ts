/**
 * Typed domain contracts for watchers and notifications, mirroring
 * backend/app/modules/notifications/schemas.py.
 *
 * Notifications are created by the backend, in the same transaction as the
 * change they announce. The client only reads them and marks them read.
 */

import type { WorkspaceKind } from "@/types/workspace";

/**
 * `unblocked`: the last unfinished task blocking one assigned to them was done.
 * `completed`: a task was moved to Done and a workspace automation rule names them.
 */
export type NotificationKind =
  | "assigned"
  | "commented"
  | "mentioned"
  | "unblocked"
  | "completed";

/** Who did it, or who is watching: a name to recognise, never an email. */
export interface NotificationPerson {
  id: string;
  display_name: string;
}

export interface AppNotification {
  id: string;
  kind: NotificationKind;
  /** `null` only if the account is gone. */
  actor: NotificationPerson | null;
  task: { id: string; title: string };
  /** Enough to build the task's address. */
  workspace: { id: string; name: string; kind: WorkspaceKind; slug: string | null };
  comment_id: string | null;
  /** The start of the comment, mentions shown as `@Name`. */
  excerpt: string | null;
  read_at: string | null;
  created_at: string;
}

/** Paginated envelope, newest first, with the unread count for the badge. */
export interface NotificationListResponse {
  items: AppNotification[];
  total: number;
  unread: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface UnreadCount {
  count: number;
}

/** Who follows a task, and whether the caller does. */
export interface Watchers {
  items: NotificationPerson[];
  watching: boolean;
}
