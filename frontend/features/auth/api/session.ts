/**
 * Session reads for server components.
 *
 * A session is only ever *read* here. The frontend never stores or inspects a
 * token: it asks the backend who the caller is and treats that answer as the
 * only routing signal it has. Backend authorization stays authoritative
 * (architecture doc section 8.2).
 */

import { cache } from "react";
import { ApiError, apiClient } from "@/lib/api/client";
import type { User } from "@/types/auth";

/** Who is asking? Throws ``ApiError`` (401) when there is no usable session. */
export async function readCurrentUser(cookie?: string): Promise<User> {
  return apiClient.get<User>("/users/me", cookie ? { cookie } : {});
}

/**
 * The same answer for every component in one request.
 *
 * A layout and the page it wraps both want to know who the caller is --- the
 * shell for its name and role, the page for its id. ``cache`` deduplicates that
 * read per render pass, so one navigation costs one API call, and no component
 * can end up with a different view of the same request.
 */
export const readCurrentUserOnce = cache((cookie?: string) => readCurrentUser(cookie));

/** Whether an error means "this caller has no usable session or permission". */
export function isUnauthenticated(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}


/**
 * Best-effort variant for pages that must render either way --- such as the
 * login screen --- where every failure reads as "not signed in".
 */
export async function tryReadCurrentUser(cookie?: string): Promise<User | null> {
  try {
    return await readCurrentUser(cookie);
  } catch {
    return null;
  }
}
