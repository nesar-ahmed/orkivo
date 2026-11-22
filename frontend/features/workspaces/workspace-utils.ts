/** Labels, badges and small rules for the workspaces feature. */

import type { BadgeVariant } from "@/components/ui/badge";
import type {
  InviteStatus,
  InvitableRole,
  Workspace,
  WorkspaceCapability,
  WorkspaceKind,
  WorkspaceMember,
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
  manager: "Manager",
  member: "Member",
  viewer: "Viewer",
};

export const WORKSPACE_ROLE_BADGES: Record<WorkspaceRole, BadgeVariant> = {
  owner: "primary",
  admin: "info",
  manager: "success",
  member: "neutral",
  viewer: "neutral",
};

/**
 * One line per role, for the pickers that hand one out. Copy for people choosing
 * a role, not the rule: what a role may do is decided by the backend and arrives
 * as `capabilities`.
 */
export const WORKSPACE_ROLE_DESCRIPTIONS: Record<WorkspaceRole, string> = {
  owner: "Everything, including making owners and admins.",
  admin: "Runs the company: its people, invitations and roles up to manager.",
  manager: "Runs the work: every task, project and label.",
  member: "Adds tasks and changes the ones they created or are assigned to.",
  viewer: "Reads everything and changes nothing.",
};

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

/**
 * The pages every workspace URL can end in. A private workspace has no people or
 * automations page: it has one person, and nobody is told about their own action.
 */
export type WorkspaceSection =
  | "overview"
  | "tasks"
  | "projects"
  | "labels"
  | "activity"
  | "people"
  | "automations";

/**
 * The sections a workspace offers, in the order its tabs and sidebar show them.
 * The overview comes first: it is where a workspace's own address lands.
 */
export function workspaceSections(kind: WorkspaceKind): WorkspaceSection[] {
  return kind === "team"
    ? ["overview", "tasks", "projects", "labels", "activity", "people", "automations"]
    : ["overview", "tasks", "projects", "labels", "activity"];
}

/** Where a workspace's own address (`/app/w/acme`, `/app/personal`) lands. */
export const WORKSPACE_HOME_SECTION: WorkspaceSection = "overview";

/** Where a workspace's page lives. Falls back to tasks where a section does not apply. */
export function workspacePath(
  workspace: Pick<Workspace, "kind" | "slug">,
  section: WorkspaceSection = "tasks",
): string {
  if (workspace.kind === "personal" || !workspace.slug) {
    const shared = section === "people" || section === "automations";
    return `${PERSONAL_WORKSPACE_PATH}/${shared ? "tasks" : section}`;
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
  const section = sectionFromPath(pathname);
  if (pathname === PERSONAL_WORKSPACE_PATH || pathname.startsWith(`${PERSONAL_WORKSPACE_PATH}/`)) {
    const shared = section === "people" || section === "automations";
    return { kind: "personal", section: shared ? "tasks" : section };
  }
  const match = pathname.match(/^\/app\/w\/([^/]+)/);
  if (match?.[1]) return { kind: "team", slug: normalizeSlug(match[1]), section };
  return null;
}

/** Which section of a workspace a path is in; anything unrecognised is its tasks. */
function sectionFromPath(pathname: string): WorkspaceSection {
  if (/\/overview(\/|$)/.test(pathname)) return "overview";
  if (/\/people(\/|$)/.test(pathname)) return "people";
  if (/\/automations(\/|$)/.test(pathname)) return "automations";
  if (/\/projects(\/|$)/.test(pathname)) return "projects";
  if (/\/labels(\/|$)/.test(pathname)) return "labels";
  if (/\/activity(\/|$)/.test(pathname)) return "activity";
  return "tasks";
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

/**
 * Why a capability is missing, so a read-only screen can say the right thing:
 * the whole company is in view mode, or the caller's role does not include it.
 * Call it only once `hasCapability` has said no.
 */
export function readOnlyReason(workspace: Pick<Workspace, "status">): "suspended" | "role" {
  return workspace.status === "suspended" ? "suspended" : "role";
}

/**
 * Whether the backend says the caller may hand out `role` here right now --- and
 * therefore change or end the membership of someone who holds it.
 */
export function canGrant(
  workspace: Pick<Workspace, "grantable_roles">,
  role: WorkspaceRole,
): boolean {
  return workspace.grantable_roles.includes(role);
}

/** The roles an invitation from the caller may offer: what they grant, never ownership. */
export function invitableRoles(workspace: Pick<Workspace, "grantable_roles">): InvitableRole[] {
  return workspace.grantable_roles.filter((role): role is InvitableRole => role !== "owner");
}

/**
 * The roles a picker may offer for one person: what the caller may grant, if they
 * may change this person's role at all --- otherwise none, and the role is shown
 * rather than offered.
 */
export function assignableRoles(
  workspace: Pick<Workspace, "capabilities" | "grantable_roles">,
  member: Pick<WorkspaceMember, "role">,
): WorkspaceRole[] {
  if (!hasCapability(workspace, "change_roles") || !canGrant(workspace, member.role)) return [];
  return workspace.grantable_roles;
}
