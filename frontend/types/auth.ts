/**
 * Typed domain contracts for authentication and the platform account surface,
 * mirroring backend/app/modules/auth/schemas.py and users/schemas.py.
 *
 * No token material appears here by design: the backend transports tokens in
 * httpOnly cookies, so the frontend never sees them.
 *
 * ``platform_role`` is one of two role axes. It decides who may run the platform
 * console; it says nothing about companies, which is what ``my_role`` in
 * `types/workspace.ts` is for. Keeping them as separate types is what stops a
 * screen from mistaking an operator for a workspace admin.
 */

export type PlatformRole = "user" | "operator";

export interface User {
  id: string;
  email: string;
  display_name: string;
  platform_role: PlatformRole;
  created_at: string;
  updated_at: string;
}

/** Paginated collection envelope returned by GET /users. */
export interface UserListResponse {
  items: User[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/** Body of POST /auth/login and POST /auth/refresh. */
export interface SessionResponse {
  user: User;
  session_id: string;
  access_token_expires_at: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput extends LoginInput {
  display_name?: string;
}

export interface UserUpdateInput {
  display_name?: string;
}

/** Body of PATCH /users/{id}/platform-role. Operators only. */
export interface PlatformRoleUpdateInput {
  platform_role: PlatformRole;
}
