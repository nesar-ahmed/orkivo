import { twMerge } from "tailwind-merge";

/**
 * Join conditional class names, resolving Tailwind conflicts so the *last* one
 * wins: `cn("h-9 text-sm", "h-auto text-2xl")` yields `h-auto text-2xl`.
 *
 * Without the merge, a component's `className` override only works when the CSS
 * happens to emit the overriding utility later --- which is how a heading-sized
 * input silently rendered at body size.
 */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return twMerge(classes.filter(Boolean).join(" "));
}
