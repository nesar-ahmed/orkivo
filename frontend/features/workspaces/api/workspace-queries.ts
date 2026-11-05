/** Typed reads against the workspaces API. */

import { apiClient } from "@/lib/api/client";
import type {
  InvitationListResponse,
  InviteListResponse,
  MemberListResponse,
  TenantListResponse,
  Workspace,
  WorkspaceKind,
  WorkspaceListResponse,
} from "@/types/workspace";

export interface WorkspaceListParams {
  page?: number;
  page_size?: number;
}

export interface MemberListParams {
  page?: number;
  page_size?: number;
}

function query(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  return search.size > 0 ? `?${search.toString()}` : "";
}

/** The tenants the caller belongs to, each with the caller's role in it. */
export function fetchMyWorkspaces(
  params: WorkspaceListParams = {},
  cookie?: string,
): Promise<WorkspaceListResponse> {
  return apiClient.get<WorkspaceListResponse>(
    `/workspaces${query(params)}`,
    cookie ? { cookie } : {},
  );
}

export function fetchWorkspace(workspaceId: string, cookie?: string): Promise<Workspace> {
  return apiClient.get<Workspace>(`/workspaces/${workspaceId}`, cookie ? { cookie } : {});
}

/**
 * A company by its address, the name that appears in its URLs. A company the
 * caller is not in answers 404, exactly like one that was never registered.
 */
export function fetchWorkspaceBySlug(slug: string, cookie?: string): Promise<Workspace> {
  return apiClient.get<Workspace>(
    `/workspaces/by-slug/${encodeURIComponent(slug)}`,
    cookie ? { cookie } : {},
  );
}

/** A company's people. Any member may read the list; outsiders get 404. */
export function fetchMembers(
  workspaceId: string,
  params: MemberListParams = {},
  cookie?: string,
): Promise<MemberListResponse> {
  return apiClient.get<MemberListResponse>(
    `/workspaces/${workspaceId}/members${query(params)}`,
    cookie ? { cookie } : {},
  );
}

/** Invitation history for one tenant. Owner or admin. */
export function fetchInvites(
  workspaceId: string,
  params: MemberListParams = {},
  cookie?: string,
): Promise<InviteListResponse> {
  return apiClient.get<InviteListResponse>(
    `/workspaces/${workspaceId}/invites${query(params)}`,
    cookie ? { cookie } : {},
  );
}

/**
 * Offers addressed to the caller's own email, for the profile screen.
 *
 * This is how an invitation reaches somebody today: no mail transport, just the
 * row an admin created, waiting for the addressee to sign in.
 */
export function fetchMyInvitations(cookie?: string): Promise<InvitationListResponse> {
  return apiClient.get<InvitationListResponse>(
    "/workspaces/invitations",
    cookie ? { cookie } : {},
  );
}

export interface TenantListParams {
  search?: string;
  kind?: WorkspaceKind;
  page?: number;
  page_size?: number;
}

/**
 * The platform console's tenant list: lifecycle and head counts only.
 *
 * There is deliberately no counterpart for reading a tenant's *content* through
 * this surface --- the API does not offer it, so the console cannot grow a
 * support backdoor by accident (architecture doc section 9).
 */
export function fetchTenants(
  params: TenantListParams = {},
  cookie?: string,
): Promise<TenantListResponse> {
  return apiClient.get<TenantListResponse>(`/platform/workspaces${query(params)}`, cookie ? { cookie } : {});
}
