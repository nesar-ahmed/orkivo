/** Typed write operations against the users API. */

import { apiClient } from "@/lib/api/client";
import type { PlatformRoleUpdateInput, User, UserUpdateInput } from "@/types/auth";

/** Change the caller's own profile. There is no route to edit anyone else's. */
export function updateProfile(input: UserUpdateInput): Promise<User> {
  return apiClient.patch<User>("/users/me", input);
}

/**
 * Promote or demote an account's *platform* role. Operators only, and this is not
 * how anyone joins or leads a company --- that is `changeMemberRole`.
 */
export function updatePlatformRole(
  userId: string,
  input: PlatformRoleUpdateInput,
): Promise<User> {
  return apiClient.patch<User>(`/users/${userId}/platform-role`, input);
}
