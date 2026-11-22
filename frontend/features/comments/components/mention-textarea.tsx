"use client";

import {
  useId,
  useRef,
  useState,
  type ComponentProps,
  type KeyboardEvent,
} from "react";
import { Avatar } from "@/components/ui/avatar";
import { Textarea } from "@/components/ui/textarea";
import { mentionQueryAt } from "@/features/comments/comment-utils";
import { cn } from "@/lib/utils/cn";
import type { CommentPerson } from "@/types/comment";

/** How many suggestions show at once; typing narrows them. */
const MAX_SUGGESTIONS = 6;

/**
 * A comment textarea that suggests people after `@`.
 *
 * Type `@` and part of a name; arrow keys move through the workspace's members,
 * Enter or Tab picks, Escape closes. Picking writes `@Name` into the text and
 * reports the person through `onMention`, so the form can turn exactly those
 * names into mention tokens when it posts. The suggestions are a listbox tied to
 * the textarea (ARIA 1.2 combobox), so they are announced as they change.
 *
 * The keys it uses are only taken while suggestions are open: Ctrl/Cmd + Enter
 * keeps posting, and Enter keeps making new lines otherwise.
 */
export function MentionTextarea({
  value,
  onValueChange,
  onMention,
  people,
  onKeyDown,
  ...props
}: Omit<ComponentProps<typeof Textarea>, "value" | "onChange"> & {
  value: string;
  onValueChange: (value: string) => void;
  onMention: (person: CommentPerson) => void;
  /** Who can be mentioned: the workspace's members, other than the writer. */
  people: readonly CommentPerson[];
}) {
  const listboxId = useId();
  const ref = useRef<HTMLTextAreaElement>(null);
  const [query, setQuery] = useState<{ start: number; query: string } | null>(null);
  const [active, setActive] = useState(0);

  const term = query?.query.toLowerCase() ?? "";
  const suggestions = query
    ? people
        .filter((person) =>
          person.display_name
            .toLowerCase()
            .split(/\s+/)
            .some((word) => word.startsWith(term)) ||
          person.display_name.toLowerCase().startsWith(term),
        )
        .slice(0, MAX_SUGGESTIONS)
    : [];
  const open = suggestions.length > 0;

  function track(text: string, caret: number) {
    const next = mentionQueryAt(text, caret);
    setQuery(next);
    if (next?.query !== query?.query) setActive(0);
  }

  function pick(person: CommentPerson) {
    if (!query) return;
    const caret = ref.current?.selectionStart ?? value.length;
    const inserted = `@${person.display_name} `;
    const next = value.slice(0, query.start) + inserted + value.slice(caret);
    onValueChange(next);
    onMention(person);
    setQuery(null);
    const position = query.start + inserted.length;
    window.requestAnimationFrame(() => {
      ref.current?.focus();
      ref.current?.setSelectionRange(position, position);
    });
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (open) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        setActive((current) => (current + step + suggestions.length) % suggestions.length);
        return;
      }
      if ((event.key === "Enter" && !event.metaKey && !event.ctrlKey) || event.key === "Tab") {
        event.preventDefault();
        const person = suggestions[active];
        if (person) pick(person);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setQuery(null);
        return;
      }
    }
    onKeyDown?.(event);
  }

  const activeId = open && suggestions[active] ? `${listboxId}-${suggestions[active].id}` : undefined;

  return (
    <div className="relative">
      <Textarea
        {...props}
        ref={ref}
        value={value}
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        onChange={(event) => {
          onValueChange(event.target.value);
          track(event.target.value, event.target.selectionStart);
        }}
        onKeyDown={handleKeyDown}
        onKeyUp={(event) => {
          // Caret moves without typing (arrows, Home/End) can leave a mention.
          if (!open || !["ArrowUp", "ArrowDown"].includes(event.key)) {
            track(event.currentTarget.value, event.currentTarget.selectionStart);
          }
        }}
        onClick={(event) => track(event.currentTarget.value, event.currentTarget.selectionStart)}
        onBlur={() => window.setTimeout(() => setQuery(null), 120)}
      />
      <ul
        id={listboxId}
        role="listbox"
        aria-label="People to mention"
        hidden={!open}
        className="absolute top-full left-0 z-40 mt-1 w-64 overflow-hidden rounded-lg border border-border bg-popover p-1 shadow-md animate-pop-in"
      >
        {suggestions.map((person, index) => (
          <li
            key={person.id}
            id={`${listboxId}-${person.id}`}
            role="option"
            aria-selected={index === active}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => pick(person)}
            onMouseEnter={() => setActive(index)}
            className={cn(
              "flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm",
              index === active && "bg-muted",
            )}
          >
            <Avatar name={person.display_name} seed={person.id} size="xs" />
            <span className="truncate">{person.display_name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
