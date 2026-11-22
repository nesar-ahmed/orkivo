import { MessageSquare } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ActivityItem } from "@/features/activity/components/activity-item";
import { isShownAsComment } from "@/features/activity/activity-utils";
import type { TaskDiscussionData } from "@/features/comments/api/task-discussion-data";
import { CommentCard } from "@/features/comments/components/comment-card";
import { CommentComposer } from "@/features/comments/components/comment-composer";
import { WatchButton } from "@/features/notifications/components/watch-button";
import type { ActivityEvent } from "@/types/activity";
import type { CommentPerson, TaskComment } from "@/types/comment";

type Entry =
  | { kind: "comment"; at: string; comment: TaskComment }
  | { kind: "event"; at: string; event: ActivityEvent };

/**
 * Everything said and done about one task, in the order it happened: comments
 * as cards, and the task's history --- created, moved, assigned, deleted
 * comments --- as lines between them. A comment's own "added" and "edited"
 * events are left out, because its card already says both.
 *
 * Rendered beside the task's edit form rather than inside it, so writing a
 * comment never interacts with unsaved edits to the task.
 *
 * `canComment` is the workspace's `comment` (a viewer, or view mode, reads only),
 * and `readOnly` says which of the two it is when it is missing; `canModerate` is
 * `manage`, which lets owners and admins delete anyone's comment.
 * `people` are the workspace's members, offered after `@`; the viewer is left
 * out, since mentioning yourself tells nobody anything.
 */
export function TaskDiscussion({
  taskId,
  data,
  viewerId,
  people,
  canComment,
  readOnly,
  canModerate,
}: {
  taskId: string;
  data: TaskDiscussionData;
  viewerId: string | null;
  people: readonly CommentPerson[];
  canComment: boolean;
  readOnly: "suspended" | "role";
  canModerate: boolean;
}) {
  const mentionable = people.filter((person) => person.id !== viewerId);
  const entries: Entry[] = [
    ...data.comments.map((comment) => ({
      kind: "comment" as const,
      at: comment.created_at,
      comment,
    })),
    ...data.activity
      .filter((event) => !isShownAsComment(event))
      .map((event) => ({ kind: "event" as const, at: event.created_at, event })),
  ].sort((a, b) => a.at.localeCompare(b.at));

  const olderHidden =
    data.commentTotal > data.comments.length || data.activityTotal > data.activity.length;

  return (
    <section aria-labelledby="discussion-heading" className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <MessageSquare aria-hidden="true" className="size-4 text-muted-foreground" />
        <h2 id="discussion-heading" className="text-sm font-semibold text-foreground">
          Comments and history
        </h2>
        <Badge variant="neutral">{data.commentTotal}</Badge>
        {data.watchers ? (
          <span className="ml-auto">
            <WatchButton taskId={taskId} initial={data.watchers} />
          </span>
        ) : null}
      </div>

      {data.loadError ? (
        <p role="alert" className="rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
          {data.loadError}
        </p>
      ) : (
        <>
          {olderHidden ? (
            <p className="text-xs text-muted-foreground">
              Showing the latest 100 comments and changes.
            </p>
          ) : null}
          <ol className="flex flex-col gap-3">
            {entries.map((entry) =>
              entry.kind === "comment" ? (
                <li key={`c-${entry.comment.id}`}>
                  <CommentCard
                    comment={entry.comment}
                    canEdit={canComment && entry.comment.author?.id === viewerId}
                    canDelete={
                      canComment && (entry.comment.author?.id === viewerId || canModerate)
                    }
                    people={mentionable}
                  />
                </li>
              ) : (
                <li key={`e-${entry.event.id}`} className="px-3">
                  <ActivityItem event={entry.event} inTask />
                </li>
              ),
            )}
          </ol>
        </>
      )}

      {canComment ? (
        <CommentComposer taskId={taskId} people={mentionable} />
      ) : (
        <p className="text-xs text-muted-foreground">
          {readOnly === "suspended"
            ? "View mode: comments can be read, but not added or changed."
            : "Your role lets you read the conversation, but not take part in it."}
        </p>
      )}
    </section>
  );
}
