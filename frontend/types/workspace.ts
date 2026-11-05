/**
 * Typed domain contracts for workspaces: tenancy, membership and invitations.
 *
 * Mirrors backend/app/modules/workspaces/schemas.py. A workspace is the tenant;
 * ``my_role`` is what the backend says the caller may do inside it, and the
 * frontend uses it only to decide what to render --- the API re-checks every
 * operation (architecture doc 8.2).
 */

export type WorkspaceKind = "personal" | "team";

export type WorkspaceStatus = "active" | "suspended";

/** Authority inside one tenant. Distinct from the platform role in `auth.ts`. */
export type WorkspaceRole = "owner" | "admin" | "member";

export type InviteStatus = "pending" | "accepted" | "declined" | "revoked";

interface WorkspaceFields {
  id: string;
  kind: WorkspaceKind;
  name: string;
  /** The tenant's address. Only a company has one. */
  slug: string | null;
  status: WorkspaceStatus;
  created_at: string;
  updated_at: string;
}

/** A tenant as its member sees it, including the caller's standing. */
export interface Workspace extends WorkspaceFields {
  my_role: WorkspaceRole;
}

export interface WorkspaceMember {
  id: string;
  user_id: string;
  email: string;
  display_name: string;
  role: WorkspaceRole;
  joined_at: string;
}

/** An invitation as the tenant sees it. */
export interface WorkspaceInvite {
  id: string;
  email: string;
  role: WorkspaceRole;
  status: InviteStatus;
  created_at: string;
  resolved_at: string | null;
}

/** An invitation as its addressee sees it: the company, and who opened it. */
export interface WorkspaceInvitation {
  id: string;
  workspace_id: string;
  workspace_name: string;
  workspace_slug: string | null;
  role: WorkspaceRole;
  invited_by_name: string | null;
  created_at: string;
}

/** A tenant in the platform console: lifecycle and head count, never content. */
export interface TenantAdmin extends WorkspaceFields {
  member_count: number;
  operator_note: string | null;
}

interface ListEnvelope<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export type WorkspaceListResponse = ListEnvelope<Workspace>;
export type MemberListResponse = ListEnvelope<WorkspaceMember>;
export type InviteListResponse = ListEnvelope<WorkspaceInvite>;
export type TenantListResponse = ListEnvelope<TenantAdmin>;

/** Not paginated: a person is invited by a handful of companies at a time. */
export interface InvitationListResponse {
  items: WorkspaceInvitation[];
}

export interface WorkspaceCreateInput {
  name: string;
  slug: string;
}

export interface WorkspaceUpdateInput {
  name: string;
}

/** What an invitation may offer. Ownership is never invited. */
export type InvitableRole = "member" | "admin";

export interface InviteInput {
  email: string;
  role?: InvitableRole;
}

export interface MemberRoleUpdate {
  role: WorkspaceRole;
}

export interface SuspensionUpdate {
  note?: string | null;
}
