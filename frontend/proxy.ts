/**
 * Route guard --- convenience routing, not a security control.
 *
 * The backend is authoritative for authentication and authorization
 * (architecture doc 8.2): every protected read is refused there, and the
 * `/app` layout re-checks the session against the API before it renders. What
 * happens here only avoids shipping a product page to someone the layout is
 * going to redirect anyway, and keeps the public surface reachable.
 *
 * Three shapes:
 *
 * * `/` is the landing page and public. A signed-in visitor is sent into the
 *   product instead of being shown a page that invites them to sign in.
 * * `/app/**` requires a session; anonymous visitors are sent to `/login` with
 *   the path they wanted, validated on the way back.
 * * anything else is left alone, so Next answers its own 404.
 *
 * The signal is the *presence* of the access cookie, which the browser drops
 * when it expires. It is never read or validated here --- it is httpOnly, and no
 * signing key belongs on this side of the boundary.
 *
 * Renewal is not done here either: the refresh cookie is scoped to the API's
 * `/auth` path, so a navigation never carries it. Renewal lives in the browser
 * transport (`lib/api/client.ts`) and in `SessionRecovery` on the login screen.
 */

import { NextResponse, type NextRequest } from "next/server";

import {
  DEFAULT_POST_AUTH_PATH,
  isAppPath,
  isPublicPath,
  safeRedirectTarget,
} from "@/features/auth/auth-policy";

/** The access token cookie, named to match `app/modules/auth/cookies.py`. */
const ACCESS_COOKIE = "orkivo_access";

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const signedIn = request.cookies.has(ACCESS_COOKIE);

  // Public surface: the landing page and the auth screens.
  if (isPublicPath(pathname)) {
    // A signed-in visitor gets the product, not a page inviting them to sign in.
    if (signedIn) return NextResponse.redirect(new URL(DEFAULT_POST_AUTH_PATH, request.url));
    return NextResponse.next();
  }

  if (isAppPath(pathname)) {
    if (signedIn) return NextResponse.next();
    const login = new URL("/login", request.url);
    login.searchParams.set("next", safeRedirectTarget(`${pathname}${search}`));
    return NextResponse.redirect(login);
  }

  // Unknown paths are not a session problem for the guard to invent.
  return NextResponse.next();
}

export const config = {
  // Pages only: skip static assets and anything with a file extension.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.).*)"],
};
