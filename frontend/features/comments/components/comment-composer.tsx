"use client";

import { useState, useTransition, type FormEvent, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { addComment } from "@/features/comments/api/comment-mutations";
import { COMMENT_MAX_LENGTH, bodyWithTokens } from "@/features/comments/comment-utils";
import { MentionTextarea } from "@/features/comments/components/mention-textarea";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { CommentPerson } from "@/types/comment";

/**
 * Say something on a task. Ctrl/Cmd + Enter posts, like saving the task itself.
 * Type `@` to mention a member: they are told, and readers see their name.
 *
 * Its own form, deliberately outside the task's edit form: posting a comment
 * never submits (or is blocked by) unsaved edits to the task above it.
 */
export function CommentComposer({
  taskId,
  people,
}: {
  taskId: string;
  /** Who can be mentioned. */
  people: readonly CommentPerson[];
}) {
  const router = useRouter();
  const [body, setBody] = useState("");
  // The names picked from the suggestions, and who they are: only these become
  // mention tokens, so typing "@Sam" by hand never mentions anyone by accident.
  const [picked, setPicked] = useState<ReadonlyMap<string, string>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const canPost = body.trim().length > 0 && !isPending;

  function post() {
    if (!canPost) return;
    startTransition(async () => {
      try {
        await addComment(taskId, { body: bodyWithTokens(body.trim(), picked) });
        setBody("");
        setPicked(new Map());
        setError(null);
        router.refresh();
      } catch (err) {
        const feedback = feedbackFromError(err, "The comment could not be posted.");
        setError(feedback.fieldErrors.body ?? feedback.generalError);
      }
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    post();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      post();
    }
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Add a comment" className="flex flex-col gap-2">
      <label htmlFor="comment-body" className="sr-only">
        Comment
      </label>
      <MentionTextarea
        id="comment-body"
        value={body}
        rows={3}
        maxLength={COMMENT_MAX_LENGTH}
        placeholder="Write a comment… Type @ to mention someone."
        onValueChange={setBody}
        onMention={(person) =>
          setPicked((current) => new Map(current).set(person.display_name, person.id))
        }
        people={people}
        onKeyDown={handleKeyDown}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? "comment-error" : undefined}
        disabled={isPending}
      />
      {error ? (
        <p id="comment-error" role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}
      <div className="flex items-center justify-end gap-3">
        <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
          <Kbd>Ctrl</Kbd>+<Kbd>Enter</Kbd> to post
        </span>
        <Button type="submit" size="sm" disabled={!canPost}>
          {isPending ? "Posting…" : "Comment"}
        </Button>
      </div>
    </form>
  );
}
