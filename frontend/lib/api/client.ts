/**
 * Centralized API access (architecture doc 8.2).
 *
 * All data access goes through this client: typed, with consistent handling of
 * the backend error contract `{ "error": { "code", "message", "details" } }`.
 *
 * Authentication uses httpOnly session cookies (see the backend's
 * `app/modules/auth/cookies.py`). In the browser the cookie jar attaches them by
 * itself and the CSRF header below satisfies the backend's guard. Server
 * rendering has no jar to speak of, so server code forwards the incoming
 * `Cookie` header through the `cookie` request option --- see
 * `getServerCookieHeader()` in `lib/api/server-cookies.ts`. No token ever lives
 * in JavaScript, and frontend routing is never treated as the security boundary.
 *
 * Session renewal is part of the transport rather than of a page: the access
 * cookie expires after 15 minutes while the refresh session lasts 30 days, and
 * only the browser can spend it --- the refresh cookie is scoped to the API's
 * `/auth` path, so Next.js server code and the route proxy never receive it. A
 * 401 on a browser call therefore renews once and replays, instead of logging
 * anyone out. See `renewSession()` below for the reuse-detection constraint
 * that shapes this.
 */

import { API_BASE_URL } from "@/lib/config/env";
import type { ApiErrorDetail } from "@/types/task";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: ApiErrorDetail[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Header the backend's CSRF guard requires on cookie-authenticated state
 * changes. A cross-site request cannot set it, and cookies are `SameSite=Lax`.
 */
export const CSRF_HEADER_NAME = "X-Orkivo-Request";
export const CSRF_HEADER_VALUE = "1";

/** What a renewal attempt ended as. ``deferred`` means another tab is renewing. */
export type RenewalOutcome = "renewed" | "failed" | "deferred";

/** How long a cross-tab renewal claim stays interesting to the other tabs. */
const RENEWAL_CLAIM_KEY = "orkivo.session-renewal";
const RENEWAL_CLAIM_WINDOW_MS = 5_000;

let renewalInFlight: Promise<RenewalOutcome> | null = null;

interface ErrorPayload {
  error?: { code?: string; message?: string; details?: ApiErrorDetail[] };
}

function isErrorPayload(value: unknown): value is ErrorPayload {
  return typeof value === "object" && value !== null && "error" in value;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Forwarded verbatim on server-rendered reads; omit in the browser. */
  cookie?: string;
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
  attempt: 0 | 1 = 0,
): Promise<T> {
  const { method = "GET", body, cookie } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["content-type"] = "application/json";
  // Mutations must carry the CSRF header. GET requests do not need it, and
  // forwarding the browser's own header on a server read is harmless.
  if (method !== "GET") headers[CSRF_HEADER_NAME] = CSRF_HEADER_VALUE;
  if (cookie) headers.cookie = cookie;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: Object.keys(headers).length > 0 ? headers : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      // Application data is always read fresh from the backend.
      cache: "no-store",
      // The session cookies are the credential: without this they are not sent
      // to the API's port.
      credentials: "include",
    });
  } catch {
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "Could not reach the Orkivo API. Is the backend running on port 8000?",
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    // An expired access token is the one failure the browser can repair itself:
    // spend the refresh session and replay the call once.
    if (canRetryAfterRenewal(path, options, response.status, attempt)) {
      const outcome = await renewSession();
      if (outcome === "renewed" || outcome === "deferred") {
        // ``deferred``: another tab holds the rotation. Give its new cookie a
        // moment to arrive instead of replaying a token that was already used.
        if (outcome === "deferred") await waitForOtherTab();
        return request<T>(path, options, 1);
      }
    }

    const errorBody = isErrorPayload(payload) ? payload.error : undefined;
    throw new ApiError(
      response.status,
      errorBody?.code ?? "UNKNOWN_ERROR",
      errorBody?.message ?? `The request failed (HTTP ${response.status}).`,
      errorBody?.details ?? [],
    );
  }

  return payload as T;
}

/**
 * Whether a failed call is worth renewing for.
 *
 * Browser calls only, once, and never for the auth endpoints themselves: a
 * rejected login is a wrong password rather than a stale token, and renewing
 * there would rotate a session the caller has no business spending.
 */
function canRetryAfterRenewal(
  path: string,
  options: RequestOptions,
  status: number,
  attempt: 0 | 1,
): boolean {
  if (status !== 401 || attempt !== 0) return false;
  if (path.startsWith("/auth/")) return false;
  // Server rendering forwards the visitor's own cookies and has no jar to renew
  // into; only the browser holds the refresh credential.
  if (options.cookie !== undefined) return false;
  return canRenewSession();
}

/** Whether a renewal can run at all: a browser, with a cookie jar to fill. */
export function canRenewSession(): boolean {
  return typeof window !== "undefined";
}

/**
 * Trade the refresh session for a fresh access cookie.
 *
 * Rotation has reuse detection: presenting an already-rotated token revokes the
 * whole session family (backend `auth/service.py`), and two tabs renewing at the
 * same instant looks exactly like theft. So renewal is single-flight per tab and
 * claimed across tabs through `localStorage`, and the loser waits for the
 * winner instead of replaying the token.
 *
 * The response body is discarded on purpose: no token material is read, and the
 * new credential lands in the jar where JavaScript cannot reach it.
 */
export function renewSession(): Promise<RenewalOutcome> {
  if (!canRenewSession()) return Promise.resolve("failed");
  if (renewalInFlight === null) {
    renewalInFlight = performRenewal().finally(() => {
      renewalInFlight = null;
    });
  }
  return renewalInFlight;
}

/** Short pause so another tab's renewed cookie can land before we replay. */
export function waitForOtherTab(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 400));
}

async function performRenewal(): Promise<RenewalOutcome> {
  if (!claimRenewal()) return "deferred";

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { [CSRF_HEADER_NAME]: CSRF_HEADER_VALUE },
      // The refresh cookie is the credential: without this it is not sent.
      credentials: "include",
      cache: "no-store",
    });
    return response.ok ? "renewed" : "failed";
  } catch {
    // Unreachable API: the caller surfaces its own network error.
    return "failed";
  }
}

/**
 * Best-effort cross-tab claim. `localStorage` can be unavailable (private
 * mode), and a duplicate renewal is worse than none, so we proceed.
 */
function claimRenewal(): boolean {
  const now = Date.now();
  try {
    const previous = Number(window.localStorage.getItem(RENEWAL_CLAIM_KEY) ?? 0);
    if (Number.isFinite(previous) && now - previous < RENEWAL_CLAIM_WINDOW_MS) return false;
    window.localStorage.setItem(RENEWAL_CLAIM_KEY, String(now));
    return true;
  } catch {
    return true;
  }
}

/** The single API client. Server code passes `cookie` to authenticate a read. */
export const apiClient = {
  get: <T>(path: string, options: Pick<RequestOptions, "cookie"> = {}) =>
    request<T>(path, { ...options }),
  post: <T>(path: string, body: unknown, options: Pick<RequestOptions, "cookie"> = {}) =>
    request<T>(path, { method: "POST", body, ...options }),
  patch: <T>(path: string, body: unknown, options: Pick<RequestOptions, "cookie"> = {}) =>
    request<T>(path, { method: "PATCH", body, ...options }),
  delete: (path: string, options: Pick<RequestOptions, "cookie"> = {}) =>
    request<void>(path, { method: "DELETE", ...options }),
};
