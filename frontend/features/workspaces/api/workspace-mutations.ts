/** Typed writes against the workspaces API. */

import { apiClient } from "@/lib/api/client";
import type {
  InviteInput,
  MemberRoleUpdate,
  SuspensionUpdate,
  TenantAdmin,
  Workspace,
  WorkspaceCreateInput,
  WorkspaceInvite,
  WorkspaceMember,
  WorkspaceUpdateInput,
} from "@/types/workspace";

/** Open a company. The caller becomes its owner. */
export function createWorkspace(input: WorkspaceCreateInput): Promise<Workspace> {
  return apiClient.post<Workspace>("/workspaces", input);
}

export function renameWorkspace(
  workspaceId: string,
  input: WorkspaceUpdateInput,
): Promise<Workspace> {
  return apiClient.patch<Workspace>(`/workspaces/${workspaceId}`, input);
}

/**
 * Open the tenant to an address. Nothing is sent: the addressee finds the offer
 * in their own profile, which is what makes the flow work before email exists.
 */
export function inviteMember(
  workspaceId: string,
  input: InviteInput,
): Promise<WorkspaceInvite> {
  return apiClient.post<WorkspaceInvite>(`/workspaces/${workspaceId}/invites`, input);
}

export function revokeInvitation(
  workspaceId: string,
  inviteId: string,
): Promise<void> {
  return apiClient.delete(`/workspaces/${workspaceId}/invites/${inviteId}`);
}

/** Claim an offer addressed to the caller. Returns the tenant now joined. */
export function acceptInvitation(invitationId: string): Promise<Workspace> {
  return apiClient.post<Workspace>(`/workspaces/invitations/${invitationId}/accept`, {});
}

export function declineInvitation(invitationId: string): Promise<void> {
  return apiClient.post<void>(`/workspaces/invitations/${invitationId}/decline`, {});
}

/** Move someone between owner, admin and member. Owners only. */
export function changeMemberRole(
  workspaceId: string,
  userId: string,
  input: MemberRoleUpdate,
): Promise<WorkspaceMember> {
  return apiClient.patch<WorkspaceMember>(
    `/workspaces/${workspaceId}/members/${userId}/role`,
    input,
  );
}

/** Remove a member --- or leave, when it is the caller's own id. */
export function removeMember(workspaceId: string, userId: string): Promise<void> {
  return apiClient.delete(`/workspaces/${workspaceId}/members/${userId}`);
}

/**
 * Platform lifecycle switches. Reversible, and no membership is destroyed ---
 * which is the difference between suspending a company and deleting it.
 */
export function suspendTenant(
  workspaceId: string,
  input: SuspensionUpdate = {},
): Promise<TenantAdmin> {
  return apiClient.post<TenantAdmin>(`/platform/workspaces/${workspaceId}/suspend`, input);
}

export function activateTenant(
  workspaceId: string,
  input: SuspensionUpdate = {},
): Promise<TenantAdmin> {
  return apiClient.post<TenantAdmin>(`/platform/workspaces/${workspaceId}/activate`, input);
}
