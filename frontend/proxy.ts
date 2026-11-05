import { NextResponse, type NextRequest } from "next/server";

import {
  DEFAULT_POST_AUTH_PATH,
  LANDING_PATH,
  isAppPath,
  isPublicPath,
  safeRedirectTarget,
} from "@/features/auth/auth-policy";
import { normalizeSlug } from "@/features/workspaces/workspace-utils";

/** The access token cookie, named to match `app/modules/auth/cookies.py`. */
const ACCESS_COOKIE = "orkivo_access";

/** The company-slug segment of an in-app path: `/app/w/<slug>/...`. */
const COMPANY_SLUG_SEGMENT = /^\/app\/w\/([^/]+)(?:\/|$)/;

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const signedIn = request.cookies.has(ACCESS_COOKIE);

  // Public surface: the landing page and the auth screens.
  if (isPublicPath(pathname)) {
    // A signed-in visitor gets the product, not a page inviting them to sign
    // in --- but only on the landing page. Auth screens answer every visitor
    // with a form, or with their page's own API-verified redirect; bouncing
    // one from here would loop when the cookie outlives its session.
    if (signedIn && pathname === LANDING_PATH) {
      return NextResponse.redirect(new URL(DEFAULT_POST_AUTH_PATH, request.url));
    }
    return NextResponse.next();
  }

  if (isAppPath(pathname)) {
    // One spelling per company address: an upper-case or escaped slug is the
    // same tenant, and the shell's own links use the canonical form. Sending
    // the browser to that form here means the URL bar, the switcher and every
    // bookmark agree, whatever was typed.
    const typed = COMPANY_SLUG_SEGMENT.exec(pathname);
    if (typed) {
      const canonical = normalizeSlug(typed[1]);
      if (canonical !== typed[1]) {
        const target = new URL(request.url);
        target.pathname = pathname.replace(typed[1], canonical);
        return NextResponse.redirect(target);
      }
    }

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
