/** Labels, badges and small rules for the workspaces feature. */

import type { BadgeVariant } from "@/components/ui/badge";
import type {
  InviteStatus,
  InvitableRole,
  WorkspaceKind,
  WorkspaceRole,
  WorkspaceStatus,
} from "@/types/workspace";

export const WORKSPACE_KIND_LABELS: Record<WorkspaceKind, string> = {
  personal: "Private",
  team: "Company",
};

export const WORKSPACE_ROLE_LABELS: Record<WorkspaceRole, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
};

export const WORKSPACE_ROLE_BADGES: Record<WorkspaceRole, BadgeVariant> = {
  owner: "primary",
  admin: "info",
  member: "neutral",
};

/**
 * Roles a picker may offer. Ownership is excluded because it is transferred by an
 * existing owner and never granted by an invitation --- the backend's contract
 * says the same thing, so the control cannot present a choice that would fail.
 */
export const ASSIGNABLE_ROLES: WorkspaceRole[] = ["owner", "admin", "member"];
export const INVITABLE_ROLES: InvitableRole[] = ["member", "admin"];

export const WORKSPACE_STATUS_LABELS: Record<WorkspaceStatus, string> = {
  active: "Active",
  suspended: "Suspended",
};

export const WORKSPACE_STATUS_BADGES: Record<WorkspaceStatus, BadgeVariant> = {
  active: "success",
  suspended: "danger",
};

export const INVITE_STATUS_LABELS: Record<InviteStatus, string> = {
  pending: "Waiting",
  accepted: "Joined",
  declined: "Declined",
  revoked: "Revoked",
};

export const INVITE_STATUS_BADGES: Record<InviteStatus, BadgeVariant> = {
  pending: "warning",
  accepted: "success",
  declined: "neutral",
  revoked: "neutral",
};

/**
 * Whether this tenant can hold people beyond its owner.
 *
 * Mirrors the backend rule that a personal workspace refuses invitations; used
 * only to hide a control that would be refused.
 */
export function isShared(kind: WorkspaceKind): boolean {
  return kind === "team";
}

/** A display name for a tenant, for lists that mix personal and shared ones. */
export function workspaceTitle(name: string, kind: WorkspaceKind): string {
  return kind === "personal" ? `${name} (private)` : name;
}
