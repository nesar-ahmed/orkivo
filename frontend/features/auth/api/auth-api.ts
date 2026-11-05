/** Auth calls made from the browser. The httpOnly cookies are the credential. */

import { apiClient } from "@/lib/api/client";
import type { LoginInput, RegisterInput, SessionResponse, User } from "@/types/auth";

export function login(input: LoginInput): Promise<SessionResponse> {
  return apiClient.post<SessionResponse>("/auth/login", input);
}

export function register(input: RegisterInput): Promise<User> {
  return apiClient.post<User>("/auth/register", input);
}

export function logout(): Promise<void> {
  // An empty body: the endpoint identifies the session from the cookies.
  return apiClient.post<void>("/auth/logout", {});
}

/**
 * Trade the long-lived refresh session for a new access cookie.
 *
 * Kept in the transport layer (`lib/api/client`) because it must not recurse
 * through the 401 retry and because the response body is deliberately unread:
 * the renewed credential goes to the cookie jar, never to JavaScript.
 */
export { renewSession } from "@/lib/api/client";
