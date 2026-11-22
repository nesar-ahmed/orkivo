"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { deleteComment, editComment } from "@/features/comments/api/comment-mutations";
import {
  COMMENT_MAX_LENGTH,
  bodyForEditing,
  bodyWithTokens,
  commentSegments,
} from "@/features/comments/comment-utils";
import { MentionTextarea } from "@/features/comments/components/mention-textarea";
import { formatTimestamp } from "@/features/tasks/task-utils";
import { ApiError } from "@/lib/api/client";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { CommentPerson, TaskComment } from "@/types/comment";

/** The names a comment already mentions, and who they are, for editing it. */
function mentionedNames(comment: TaskComment): ReadonlyMap<string, string> {
  return new Map(comment.mentions.map((person) => [person.display_name, person.id]));
}

/**
 * One comment: who, when, whether it was edited, and what it says --- with
 * mentions shown as names (or "@someone" for a person no longer a member).
 *
 * Its author may edit it in place; its author --- or an owner or admin
 * moderating --- may delete it, after confirming, since a deleted comment is gone
 * for good (the activity log keeps that it existed, never what it said). The page
 * decides `canEdit` / `canDelete` from the workspace's capabilities and the
 * viewer; the API re-checks both.
 */
export function CommentCard({
  comment,
  canEdit,
  canDelete,
  people,
}: {
  comment: TaskComment;
  canEdit: boolean;
  canDelete: boolean;
  /** Who can be mentioned when editing. */
  people: readonly CommentPerson[];
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => bodyForEditing(comment.body, comment.mentions));
  const [picked, setPicked] = useState<ReadonlyMap<string, string>>(() => mentionedNames(comment));
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const author = comment.author?.display_name ?? "A former member";

  function save() {
    const body = draft.trim();
    if (!body) return;
    startTransition(async () => {
      try {
        await editComment(comment.id, { body: bodyWithTokens(body, picked) });
        setEditing(false);
        setError(null);
        router.refresh();
      } catch (err) {
        const feedback = feedbackFromError(err, "The comment could not be saved.");
        setError(feedback.fieldErrors.body ?? feedback.generalError);
      }
    });
  }

  function remove() {
    startTransition(async () => {
      try {
        await deleteComment(comment.id);
        toast("Comment deleted");
        router.refresh();
      } catch (err) {
        toast.error("The comment could not be deleted.", {
          description: err instanceof ApiError ? err.message : undefined,
        });
      }
    });
  }

  return (
    <article
      aria-label={`Comment by ${author}`}
      className="flex gap-3 rounded-xl border border-border bg-card p-3 shadow-xs"
    >
      <Avatar name={author} seed={comment.author?.id} size="sm" className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <header className="flex flex-wrap items-center gap-x-2 text-xs">
          <span className="text-sm font-medium text-foreground">{author}</span>
          <time dateTime={comment.created_at} className="text-muted-foreground">
            {formatTimestamp(comment.created_at)}
          </time>
          {comment.edited_at ? <span className="text-muted-foreground">(edited)</span> : null}
          {!editing && (canEdit || canDelete) ? (
            <span className="ml-auto flex gap-0.5">
              {canEdit ? (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Edit comment"
                  onClick={() => {
                    setDraft(bodyForEditing(comment.body, comment.mentions));
                    setPicked(mentionedNames(comment));
                    setEditing(true);
                  }}
                  disabled={isPending}
                >
                  <Pencil aria-hidden="true" />
                </Button>
              ) : null}
              {canDelete ? (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Delete comment"
                  onClick={() => setConfirming(true)}
                  disabled={isPending}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              ) : null}
            </span>
          ) : null}
        </header>

        {editing ? (
          <div className="mt-2 flex flex-col gap-2">
            <label htmlFor={`comment-edit-${comment.id}`} className="sr-only">
              Edit comment
            </label>
            <MentionTextarea
              id={`comment-edit-${comment.id}`}
              value={draft}
              rows={3}
              maxLength={COMMENT_MAX_LENGTH}
              autoFocus
              onValueChange={setDraft}
              onMention={(person) =>
                setPicked((current) => new Map(current).set(person.display_name, person.id))
              }
              people={people}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                  event.preventDefault();
                  save();
                } else if (event.key === "Escape") {
                  setEditing(false);
                }
              }}
              disabled={isPending}
            />
            {error ? (
              <p role="alert" className="text-xs text-danger">
                {error}
              </p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditing(false)}
                disabled={isPending}
              >
                Cancel
              </Button>
              <Button size="sm" onClick={save} disabled={isPending || !draft.trim()}>
                {isPending ? "Saving…" : "Save"}
              </Button>
            </div>
          </div>
        ) : (
          <p className="mt-1 text-sm leading-relaxed whitespace-pre-wrap break-words text-foreground">
            {commentSegments(comment.body, comment.mentions).map((segment, index) =>
              segment.kind === "text" ? (
                segment.text
              ) : (
                <span
                  key={index}
                  className="rounded bg-primary/10 px-0.5 font-medium text-primary"
                >
                  @{segment.person?.display_name ?? "someone"}
                </span>
              ),
            )}
          </p>
        )}
      </div>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Delete this comment?"
        description="It is removed for everyone. The task's history keeps that a comment was deleted, but not what it said."
        confirmLabel="Delete comment"
        onConfirm={remove}
      />
    </article>
  );
}
