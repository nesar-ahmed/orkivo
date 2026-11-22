/**
 * Typed writes against the comments API. Each one is also recorded in the task's
 * activity log by the backend, in the same transaction.
 */

import { ApiError, apiClient } from "@/lib/api/client";
import type { CommentInput, TaskComment } from "@/types/comment";

export function addComment(taskId: string, input: CommentInput): Promise<TaskComment> {
  return apiClient.post<TaskComment>(`/tasks/${taskId}/comments`, input);
}

/** Change what you said. The author only. */
export function editComment(commentId: string, input: CommentInput): Promise<TaskComment> {
  return apiClient.patch<TaskComment>(`/comments/${commentId}`, input);
}

/** Remove a comment: its author, or an owner or admin. */
export function deleteComment(commentId: string): Promise<void> {
  return apiClient.delete(`/comments/${commentId}`);
}

/** Whether an API error means "you can see this comment but not change it". */
export function isCommentForbidden(error: unknown): boolean {
  return error instanceof ApiError && error.code === "COMMENT_FORBIDDEN";
}
