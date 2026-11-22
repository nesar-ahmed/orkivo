/** Typed reads against the comments API. */

import { apiClient } from "@/lib/api/client";
import type { CommentListResponse } from "@/types/comment";

export interface CommentListParams {
  page?: number;
  page_size?: number;
}

/** A task's conversation, oldest first. A task the caller cannot reach answers 404. */
export function fetchComments(
  taskId: string,
  params: CommentListParams = {},
  cookie?: string,
): Promise<CommentListResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient.get<CommentListResponse>(
    `/tasks/${taskId}/comments${suffix}`,
    cookie ? { cookie } : {},
  );
}
