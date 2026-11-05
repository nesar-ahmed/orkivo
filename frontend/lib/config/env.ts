/** Runtime configuration for the frontend. */

/**
 * Base URL of the Orkivo FastAPI backend (versioned REST API).
 *
 * Host name matters for authentication: session cookies are stored per host and
 * ignore the port, so the API must be reached on the *same* host the dashboard
 * is served from (``localhost``, not ``127.0.0.1``). Mixing the two makes the
 * browser drop the cookie and every request arrives unauthenticated.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
