/**
 * Resolve the company a `/app/w/[slug]` URL names, for the layout and its pages.
 *
 * Every way of not being allowed in --- a malformed address, a company that does
 * not exist, or one the caller is not a member of --- ends in the same 404 page.
 * The API already refuses to tell those apart, and this screen does not invent a
 * distinction (architecture doc 8.2, section 9). The read is cached per request,
 * so the layout and the page share one API call.
 */

import { notFound, redirect } from "next/navigation";
import { SLUG_PATTERN, normalizeSlug, readWorkspaceBySlugOnce } from "@/features/workspaces";
import { ApiError } from "@/lib/api/client";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import type { Workspace } from "@/types/workspace";

export async function loadCompany(
  params: Promise<{ slug: string }>,
): Promise<{ workspace: Workspace; cookie: string | undefined }> {
  const { slug: rawSlug } = await params;
  const slug = normalizeSlug(rawSlug);
  // A hand-typed address should read as "no such company", not as a 422.
  if (!SLUG_PATTERN.test(slug)) notFound();

  const cookie = await getServerCookieHeader();
  try {
    return { workspace: await readWorkspaceBySlugOnce(slug, cookie), cookie };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    throw error;
  }
}
