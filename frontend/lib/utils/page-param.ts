/**
 * Read a `?page=` value from the URL.
 *
 * A hand-typed value must not become a 422 from the API or an empty list: anything
 * that is not a positive integer reads as the first page, and absurdly large
 * values are capped. Pages past the end simply render the empty state.
 */
export function parsePageParam(value: string | string[] | undefined): number {
  const raw = Array.isArray(value) ? value[0] : value;
  const parsed = Number(raw ?? 1);
  if (!Number.isInteger(parsed)) return 1;
  return Math.min(Math.max(parsed, 1), 10_000);
}
