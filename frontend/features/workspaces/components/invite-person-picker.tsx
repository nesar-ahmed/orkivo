"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Search, X } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fetchInviteCandidates } from "@/features/workspaces/api/workspace-queries";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";
import type { CandidateStanding, InviteCandidate } from "@/types/workspace";

const SEARCH_DEBOUNCE_MS = 250;

const STANDING_LABELS: Record<CandidateStanding, string> = {
  member: "Already a member",
  invited: "Already invited",
};

/** Looks like a whole address --- the only way to find someone you do not work with. */
function looksLikeAddress(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

/**
 * Choose who to invite, from people who actually have an Orkivo account.
 *
 * A combobox (ARIA 1.2): type to narrow, arrow keys to move, Enter to pick,
 * Escape to close. The backend decides who may appear --- never the inviter
 * themselves, colleagues by name or part of their address, anyone else only by
 * their exact address --- so the picker can never page through the platform's
 * accounts. People already in the company, or already holding an offer, are
 * listed but cannot be picked, with the reason beside them.
 */
export function InvitePersonPicker({
  workspaceId,
  value,
  onChange,
  disabled,
  invalid,
  describedBy,
}: {
  workspaceId: string;
  value: InviteCandidate | null;
  onChange: (person: InviteCandidate | null) => void;
  disabled?: boolean;
  invalid?: boolean;
  describedBy?: string;
}) {
  const listboxId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<InviteCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState(-1);

  // Search as the person types, once they pause; also on first opening (no
  // search: the inviter's colleagues).
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      fetchInviteCandidates(workspaceId, search.trim() || undefined)
        .then((page) => {
          if (cancelled) return;
          setResults(page.items);
          setError(null);
          setActive(page.items.findIndex((person) => person.standing === null));
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setResults([]);
          setError(err instanceof ApiError ? err.message : "People could not be loaded.");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [open, search, workspaceId]);

  function pick(person: InviteCandidate) {
    if (person.standing !== null) return;
    onChange(person);
    setOpen(false);
    setSearch("");
  }

  function move(step: 1 | -1) {
    if (results.length === 0) return;
    let next = active;
    for (let tries = 0; tries < results.length; tries += 1) {
      next = (next + step + results.length) % results.length;
      if (results[next]?.standing === null) break;
    }
    setActive(next);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) setOpen(true);
      else move(1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      move(-1);
    } else if (event.key === "Enter" && open) {
      // Picking is the Enter key's job here; it must not submit the form.
      event.preventDefault();
      const person = results[active];
      if (person) pick(person);
    } else if (event.key === "Escape" && open) {
      event.preventDefault();
      setOpen(false);
    }
  }

  if (value) {
    return (
      <div className="flex items-center gap-2.5 rounded-md border border-border bg-muted/40 px-2.5 py-2">
        <Avatar name={value.display_name} seed={value.id} size="sm" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-foreground">
            {value.display_name}
          </span>
          <span className="block truncate text-xs text-muted-foreground">{value.email}</span>
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={`Choose someone other than ${value.display_name}`}
          onClick={() => {
            onChange(null);
            // Straight back to searching, where the person was a moment ago.
            window.setTimeout(() => inputRef.current?.focus(), 0);
          }}
          disabled={disabled}
        >
          <X aria-hidden="true" />
        </Button>
      </div>
    );
  }

  const term = search.trim();
  const activeId = active >= 0 && results[active] ? `${listboxId}-${results[active].id}` : undefined;

  return (
    <div className="relative">
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
      />
      <input
        ref={inputRef}
        id="invite-person"
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={open ? activeId : undefined}
        aria-invalid={invalid}
        aria-describedby={describedBy}
        autoComplete="off"
        spellCheck={false}
        value={search}
        placeholder="Name or email address"
        disabled={disabled}
        onChange={(event) => {
          setSearch(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        // Let a click on an option land before the list closes.
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onKeyDown={handleKeyDown}
        className={cn(
          "h-9 w-full rounded-md border border-border bg-card pr-2 pl-8 text-sm shadow-xs",
          "placeholder:text-muted-foreground hover:border-border-strong focus-visible:border-primary",
          "focus-visible:ring-3 focus-visible:ring-primary/20 focus-visible:outline-none",
          invalid && "border-danger",
        )}
      />

      {open ? (
        <div className="absolute top-full right-0 left-0 z-40 mt-1 overflow-hidden rounded-lg border border-border bg-popover shadow-md animate-pop-in">
          <ul id={listboxId} role="listbox" aria-label="People you can invite" className="max-h-64 overflow-y-auto p-1">
            {results.map((person, index) => {
              const unavailable = person.standing !== null;
              return (
                <li
                  key={person.id}
                  id={`${listboxId}-${person.id}`}
                  role="option"
                  aria-selected={index === active}
                  aria-disabled={unavailable || undefined}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => pick(person)}
                  onMouseEnter={() => !unavailable && setActive(index)}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm",
                    unavailable ? "cursor-default opacity-60" : "cursor-pointer",
                    index === active && !unavailable && "bg-muted",
                  )}
                >
                  <Avatar name={person.display_name} seed={person.id} size="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-foreground">
                      {person.display_name}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {person.email}
                    </span>
                  </span>
                  {person.standing ? (
                    <Badge variant="neutral">{STANDING_LABELS[person.standing]}</Badge>
                  ) : null}
                </li>
              );
            })}
          </ul>
          <p role="status" className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
            {loading
              ? "Searching…"
              : error
                ? error
                : results.length > 0
                  ? term
                    ? "Not listed? Type their full email address."
                    : "People you already work with. Type to search, or enter a full email address."
                  : looksLikeAddress(term)
                    ? "No Orkivo account uses this address. Ask them to sign up first, then invite them."
                    : term
                      ? "Nobody you work with matches. To find anyone else on Orkivo, type their full email address."
                      : "Type a name, or the full email address of someone on Orkivo."}
          </p>
        </div>
      ) : null}
    </div>
  );
}
