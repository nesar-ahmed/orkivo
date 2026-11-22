/**
 * Small rules for the comments feature, and the mention syntax on the client.
 *
 * The API stores a mention as a token, `<@user-id>` (see the backend's
 * `comments/mentions.py`): names are neither unique nor permanent. People type
 * and read names, though, so the composer shows `@Name` and converts exactly the
 * names that were picked from the suggestions back into tokens on the way out.
 */

import type { CommentPerson } from "@/types/comment";

/** Mirrors the backend's limit, so the field never accepts what the API refuses. */
export const COMMENT_MAX_LENGTH = 10_000;

const TOKEN = /<@([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})>/g;

/** A piece of a comment body: plain text, or a mention (`null` = not resolvable). */
export type CommentSegment =
  | { readonly kind: "text"; readonly text: string }
  | { readonly kind: "mention"; readonly person: CommentPerson | null };

/** Split a stored body into text and mentions, for rendering. */
export function commentSegments(
  body: string,
  mentions: readonly CommentPerson[],
): CommentSegment[] {
  const byId = new Map(mentions.map((person) => [person.id.toLowerCase(), person]));
  const segments: CommentSegment[] = [];
  let last = 0;
  for (const match of body.matchAll(TOKEN)) {
    const at = match.index ?? 0;
    if (at > last) segments.push({ kind: "text", text: body.slice(last, at) });
    segments.push({ kind: "mention", person: byId.get(match[1]!.toLowerCase()) ?? null });
    last = at + match[0].length;
  }
  if (last < body.length) segments.push({ kind: "text", text: body.slice(last) });
  return segments;
}

/**
 * A stored body as its author edits it: known mentions as `@Name`. A token for
 * someone no longer a member stays a token, so saving the edit keeps it as is.
 */
export function bodyForEditing(body: string, mentions: readonly CommentPerson[]): string {
  const byId = new Map(mentions.map((person) => [person.id.toLowerCase(), person]));
  return body.replace(TOKEN, (token, id: string) => {
    const person = byId.get(id.toLowerCase());
    return person ? `@${person.display_name}` : token;
  });
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Typed text back to a stored body: every `@Name` that was picked becomes its
 * token. Longest names first, and only at a word boundary, so `@Mo` never eats
 * the start of `@Moe`.
 */
export function bodyWithTokens(text: string, picked: ReadonlyMap<string, string>): string {
  const names = [...picked.keys()].sort((a, b) => b.length - a.length);
  let body = text;
  for (const name of names) {
    const pattern = new RegExp(`@${escapeRegExp(name)}(?![\\p{L}\\p{N}_])`, "gu");
    body = body.replace(pattern, `<@${picked.get(name)}>`);
  }
  return body;
}

/**
 * The mention being typed just before the caret, if any: `@` at the start or
 * after whitespace, followed by up to 40 non-space characters.
 */
export function mentionQueryAt(
  text: string,
  caret: number,
): { start: number; query: string } | null {
  const match = /(^|\s)@([^\s@]{0,40})$/.exec(text.slice(0, caret));
  if (!match) return null;
  return { start: caret - match[2]!.length - 1, query: match[2]! };
}
