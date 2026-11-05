/**
 * Route and password rules the frontend needs before the backend answers.
 *
 * The password bounds mirror `auth/passwords.py`; the route classification
 * mirrors the split between the public surface (`/`, `/login`, `/register`) and
 * the product surface under `/app`. Both are used by `proxy.ts`, which is only
 * ever a convenience --- the backend stays authoritative (section 8.2).
 */

export const PASSWORD_MIN_LENGTH = 12;
export const PASSWORD_MAX_LENGTH = 128;

/** Where a signed-in visitor belongs when nothing else was asked for. */
export const DEFAULT_POST_AUTH_PATH = "/app/dashboard";

/** Prefix of the authenticated product surface; `/` itself is public. */
export const APP_PREFIX = "/app";

/** The public authentication routes. */
export const AUTH_PATHS: readonly string[] = ["/login", "/register"];

/** The public marketing entry point. */
export const LANDING_PATH = "/";

/**
 * An in-app path: rooted, and not a protocol-relative or backslash variant that
 * a browser would resolve to another host.
 */
const ABSOLUTE_IN_APP_PATH = /^\/(?!\/|\\)/;

/** Whether a path is one of the public authentication screens. */
export function isAuthPath(pathname: string): boolean {
  const clean = pathname.replace(/\/$/, "");
  return AUTH_PATHS.includes(clean) || AUTH_PATHS.includes(pathname);
}

/** Whether a path belongs to the signed-in product. */
export function isAppPath(pathname: string): boolean {
  return pathname === APP_PREFIX || pathname.startsWith(`${APP_PREFIX}/`);
}

/** Whether a path is public: the landing page or an auth screen. */
export function isPublicPath(pathname: string): boolean {
  return pathname === LANDING_PATH || isAuthPath(pathname);
}

/**
 * Where a sign-in is allowed to land.
 *
 * Only an in-app path is accepted: a scheme, a host or a protocol-relative
 * "//" or "/\" target would turn the login redirect into an open redirect.
 * Public screens are refused as targets --- the landing page sends signed-in
 * visitors onward anyway, and a login screen would simply loop. A query string
 * may travel with the path; it is not what decides.
 */
export function safeRedirectTarget(value: string | null | undefined): string {
  if (!value || !ABSOLUTE_IN_APP_PATH.test(value)) return DEFAULT_POST_AUTH_PATH;
  const [pathname] = value.split(/[?#]/);
  if (isPublicPath(pathname ?? "/")) return DEFAULT_POST_AUTH_PATH;
  return value;
}
