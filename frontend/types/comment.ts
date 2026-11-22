/**
 * Typed domain contracts for comments, mirroring
 * backend/app/modules/comments/schemas.py.
 *
 * A member is mentioned by writing `<@their-user-id>` in the body: they are
 * notified, and readers see their name (from `mentions`).
 *
 * A comment lives on one task and inherits its access rule. Only its author edits
 * it; its author or an owner or admin deletes it. Commenting never changes the
 * task's `version`.
 */

/** Who wrote a comment: a name to recognise, never an email. */
export interface CommentPerson {
  id: string;
  display_name: string;
}

export interface TaskComment {
  id: string;
  task_id: string;
  /** Plain text, with mentions written as `<@user-id>` tokens. */
  body: string;
  /** `null` only if the account is gone. */
  author: CommentPerson | null;
  /** The current members the body's tokens name; anyone else reads as "@someone". */
  mentions: CommentPerson[];
  /** Set once the author changes the text. */
  edited_at: string | null;
  created_at: string;
}

/** Paginated collection envelope, oldest first. */
export interface CommentListResponse {
  items: TaskComment[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface CommentInput {
  body: string;
}
