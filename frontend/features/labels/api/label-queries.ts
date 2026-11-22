/**
 * Typed read operations against the labels API.
 *
 * Lists are read *from a workspace*; the backend answers "not found" for a
 * workspace the caller is not in, and for a label outside the caller's tenants.
 */

import { apiClient } from "@/lib/api/client";
import type { Label, LabelListResponse } from "@/types/label";

export interface LabelListParams {
  page?: number;
  page_size?: number;
}

export function fetchLabels(
  workspaceId: string,
  params: LabelListParams = {},
  cookie?: string,
): Promise<LabelListResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient.get<LabelListResponse>(
    `/workspaces/${workspaceId}/labels${suffix}`,
    cookie ? { cookie } : {},
  );
}

export function fetchLabel(labelId: string, cookie?: string): Promise<Label> {
  return apiClient.get<Label>(`/labels/${labelId}`, cookie ? { cookie } : {});
}
