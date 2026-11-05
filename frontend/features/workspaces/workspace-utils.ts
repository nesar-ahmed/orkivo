/** Labels, badges and small rules for the workspaces feature. */

import type { BadgeVariant } from "@/components/ui/badge";
import type {
  InviteStatus,
  InvitableRole,
  Workspace,
  WorkspaceCapability,
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

// --- workspace URLs ----------------------------------------------------------
//
// A company is addressed by its slug: `/app/w/acme-robotics/tasks`. The `/w/`
// segment keeps customer-chosen names out of the product's own route namespace,
// so adding a page such as `/app/reports` can never collide with a company that
// picked "reports" as its address. The private workspace has no slug and lives
// at `/app/personal`.

/** Mirrors the backend's `SLUG_PATTERN`: what a company address may look like. */
export const SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$/;

export const PERSONAL_WORKSPACE_PATH = "/app/personal";
export const COMPANY_WORKSPACE_PREFIX = "/app/w";

/** The pages every workspace URL can end in. A private workspace has no people page. */
export type WorkspaceSection = "tasks" | "people";

/** Where a workspace's page lives. Falls back to tasks where a section does not apply. */
export function workspacePath(
  workspace: Pick<Workspace, "kind" | "slug">,
  section: WorkspaceSection = "tasks",
): string {
  if (workspace.kind === "personal" || !workspace.slug) {
    return `${PERSONAL_WORKSPACE_PATH}/tasks`;
  }
  return `${COMPANY_WORKSPACE_PREFIX}/${workspace.slug}/${section}`;
}

/** Which workspace a URL points at, read from the path alone. */
export type WorkspacePathRef =
  | { kind: "personal"; section: WorkspaceSection }
  | { kind: "team"; slug: string; section: WorkspaceSection };

/**
 * Slugs are lowercase (the backend stores them that way, and `proxy.ts`
 * redirects any other spelling), so the one read from a URL is normalised the
 * same way --- otherwise `/app/w/ACME/...` would render a page the shell does
 * not recognise as the current workspace.
 */
export function normalizeSlug(raw: string): string {
  let decoded = raw;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    // A malformed escape is simply not a slug; matching will find nothing.
  }
  return decoded.toLowerCase();
}

export function workspaceRefFromPath(pathname: string): WorkspacePathRef | null {
  const section: WorkspaceSection = /\/people(\/|$)/.test(pathname) ? "people" : "tasks";
  if (pathname === PERSONAL_WORKSPACE_PATH || pathname.startsWith(`${PERSONAL_WORKSPACE_PATH}/`)) {
    return { kind: "personal", section: "tasks" };
  }
  const match = pathname.match(/^\/app\/w\/([^/]+)/);
  if (match?.[1]) return { kind: "team", slug: normalizeSlug(match[1]), section };
  return null;
}

/** The workspace a URL points at, among the ones the caller belongs to. */
export function findWorkspaceForPath(
  pathname: string,
  workspaces: readonly Workspace[],
): Workspace | null {
  const ref = workspaceRefFromPath(pathname);
  if (ref === null) return null;
  if (ref.kind === "personal") return workspaces.find((w) => w.kind === "personal") ?? null;
  return workspaces.find((w) => w.slug?.toLowerCase() === ref.slug) ?? null;
}

/** The URL of one task, inside the workspace that holds it. */
export function taskPath(workspace: Pick<Workspace, "kind" | "slug">, taskId: string): string {
  return `${workspacePath(workspace, "tasks")}/${taskId}`;
}

// --- capabilities ------------------------------------------------------------

/**
 * Whether the backend says the caller may do this here right now.
 *
 * Presentation only: it hides a control the API would refuse. The decision itself
 * --- including what a suspended company still allows --- is the backend's access
 * policy, so the frontend never restates the rules.
 */
export function hasCapability(
  workspace: Pick<Workspace, "capabilities">,
  capability: WorkspaceCapability,
): boolean {
  return workspace.capabilities.includes(capability);
}
