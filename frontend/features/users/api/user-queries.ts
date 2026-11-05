/** Typed read operations against the users API. */

import { apiClient } from "@/lib/api/client";
import type { User, UserListResponse } from "@/types/auth";

export interface UserListParams {
  search?: string;
  page?: number;
  page_size?: number;
}

/**
 * Operator-only directory of accounts, with a ``search`` over email and display
 * name plus pagination.
 *
 * This crosses tenants by design --- it exists to run the platform. The API
 * answers 403 for anyone without the operator role, so this call is never
 * expected to succeed from ordinary code paths (architecture doc section 9).
 */
export function fetchUsers(params: UserListParams = {}, cookie?: string): Promise<UserListResponse> {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient.get<UserListResponse>(`/users${suffix}`, cookie ? { cookie } : {});
}

export function fetchCurrentUser(cookie?: string): Promise<User> {
  return apiClient.get<User>("/users/me", cookie ? { cookie } : {});
}
