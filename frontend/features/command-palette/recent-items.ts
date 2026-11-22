/**
 * What the person opened recently, for the palette to offer before they type.
 *
 * Kept in this browser's `localStorage`, per account --- so two people sharing a
 * computer never see each other's --- and holding only what the person already
 * saw: a title, where it lives and its address. Nothing here grants anything: an
 * item from a workspace they have since left is dropped when read, and opening
 * any address is still checked by the API.
 */

import type { TaskStatus } from "@/types/task";
import type { WorkspaceKind } from "@/types/workspace";

export interface RecentItem {
  readonly kind: "task" | "project" | "workspace";
  readonly id: string;
  readonly label: string;
  readonly href: string;
  /** Where it lives, by name; for a workspace, nothing. */
  readonly detail?: string;
  readonly workspaceId: string;
  readonly workspaceKind: WorkspaceKind;
  readonly workspaceName: string;
  /** Tasks only, for the status icon. */
  readonly status?: TaskStatus;
}

/** How many recent items are kept and offered. */
export const RECENT_LIMIT = 5;

const keyFor = (userId: string) => `orkivo.recent.${userId}`;

/** The person's recent items in these workspaces, newest first. */
export function readRecent(userId: string, workspaceIds: ReadonlySet<string>): RecentItem[] {
  try {
    const raw = window.localStorage.getItem(keyFor(userId));
    const items: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(items)) return [];
    return (items as RecentItem[])
      .filter((item) => item && typeof item.href === "string" && workspaceIds.has(item.workspaceId))
      .slice(0, RECENT_LIMIT);
  } catch {
    // Unavailable (private mode) or unreadable: there is simply no history.
    return [];
  }
}

/** Put `item` first, once. Best effort: a full or blocked storage is not an error. */
export function rememberRecent(userId: string, item: RecentItem): void {
  try {
    const raw = window.localStorage.getItem(keyFor(userId));
    const items: unknown = raw ? JSON.parse(raw) : [];
    const earlier = Array.isArray(items) ? (items as RecentItem[]) : [];
    const next = [item, ...earlier.filter((old) => old.id !== item.id)].slice(0, RECENT_LIMIT * 4);
    window.localStorage.setItem(keyFor(userId), JSON.stringify(next));
  } catch {
    // Nothing to do: the palette works without history.
  }
}
