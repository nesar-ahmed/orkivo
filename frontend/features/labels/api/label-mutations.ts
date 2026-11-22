/**
 * Typed write operations against the labels API.
 *
 * A label is created *in* a workspace; after that it is addressed by its own id.
 * Deleting one keeps its tasks: the label is only taken off them.
 */

import { ApiError, apiClient } from "@/lib/api/client";
import type { Label, LabelCreateInput, LabelUpdateInput } from "@/types/label";

export function createLabel(workspaceId: string, input: LabelCreateInput): Promise<Label> {
  return apiClient.post<Label>(`/workspaces/${workspaceId}/labels`, input);
}

/**
 * Rename or recolor a label. Pass the `version` you read: if a colleague saved in
 * between, the API refuses with 409 `LABEL_CONFLICT`.
 */
export function updateLabel(labelId: string, input: LabelUpdateInput): Promise<Label> {
  return apiClient.patch<Label>(`/labels/${labelId}`, input);
}

/** Delete a label (owners and admins); with `version`, only if unchanged since read. */
export function deleteLabel(labelId: string, version?: number): Promise<void> {
  const suffix = version !== undefined ? `?version=${version}` : "";
  return apiClient.delete(`/labels/${labelId}${suffix}`);
}

/** Whether an API error means "another label here already has this name". */
export function isLabelNameInUse(error: unknown): boolean {
  return error instanceof ApiError && error.code === "LABEL_NAME_IN_USE";
}

/** Whether an API error means "someone else changed this label first". */
export function isLabelConflict(error: unknown): boolean {
  return error instanceof ApiError && error.code === "LABEL_CONFLICT";
}
