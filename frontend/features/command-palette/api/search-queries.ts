/**
 * Search across every workspace the caller may read. Browser only: the palette
 * asks as the person types, and cancels the question a newer one replaces.
 */

import { apiClient } from "@/lib/api/client";
import type { SearchResponse } from "@/types/search";

/** How many of each kind the palette shows. */
export const RESULTS_PER_KIND = 6;

export function searchEverywhere(term: string, signal?: AbortSignal): Promise<SearchResponse> {
  const query = new URLSearchParams({ q: term, limit: String(RESULTS_PER_KIND) });
  return apiClient.get<SearchResponse>(`/search?${query.toString()}`, { signal });
}
