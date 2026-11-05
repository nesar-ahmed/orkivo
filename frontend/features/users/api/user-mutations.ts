/** Typed write operations against the users API. */

import { apiClient } from "@/lib/api/client";
import type {
  AccountAdmin,
  AccountDisableInput,
  PlatformRoleUpdateInput,
  User,
  UserUpdateInput,
} from "@/types/auth";

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

/**
 * Stop an account: it cannot sign in, and every session it holds ends now. This is
 * how an individual is stopped --- a private workspace is never suspended.
 */
export function disableAccount(
  userId: string,
  input: AccountDisableInput = {},
): Promise<AccountAdmin> {
  return apiClient.post<AccountAdmin>(`/users/${userId}/disable`, input);
}

/** Restore an account. Its old sessions stay ended: the person signs in again. */
export function enableAccount(userId: string): Promise<AccountAdmin> {
  return apiClient.post<AccountAdmin>(`/users/${userId}/enable`, {});
}
