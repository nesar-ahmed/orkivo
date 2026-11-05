/**
 * Cookie forwarding for server-rendered requests (architecture doc 8.2).
 *
 * The backend scopes the access cookie to ``Path=/`` so the browser attaches it
 * to requests for *this* origin as well, not only to the API's port. Server
 * components read it here and hand it to the API client, which makes a
 * server-rendered read run as its visitor while no token ever reaches
 * JavaScript.
 */

import { cookies } from "next/headers";

/** The incoming ``Cookie`` header value, or ``undefined`` when there is none. */
export async function getServerCookieHeader(): Promise<string | undefined> {
  const jar = await cookies();
  const pairs = jar.getAll().map(({ name, value }) => `${name}=${decodeURIComponent(value)}`);
  return pairs.length > 0 ? pairs.join("; ") : undefined;
}
