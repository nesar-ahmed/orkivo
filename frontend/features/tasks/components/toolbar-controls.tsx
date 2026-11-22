"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ListFilter, Search } from "lucide-react";
import { buttonClasses } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils/cn";

/**
 * The controls every task toolbar is built from --- a workspace's board and a
 * person's own list alike --- so a view switch, a search box and a filter menu
 * look and behave the same wherever they appear. Each one writes to the URL; the
 * toolbar that uses it decides what the URL looks like.
 */

const ANY = "any";
const SEARCH_DEBOUNCE_MS = 300;

export interface ViewOption {
  readonly href: string;
  readonly active: boolean;
  readonly icon: ReactNode;
  readonly label: string;
}

/** A segmented control of links, one per view. Links, so each view has an address. */
export function ViewSwitch({ options }: { options: readonly ViewOption[] }) {
  return (
    <div
      role="group"
      aria-label="View"
      className="inline-flex rounded-lg border border-border bg-muted/60 p-0.5"
    >
      {options.map((option) => (
        <Link
          key={option.label}
          href={option.href}
          aria-current={option.active ? "page" : undefined}
          className={cn(
            "inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium transition-colors [&_svg]:size-4",
            option.active
              ? "bg-card text-foreground shadow-xs ring-1 ring-border"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {option.icon}
          {option.label}
        </Link>
      ))}
    </div>
  );
}

/**
 * A search box whose term lives in the URL. Typing is debounced and *replaces* the
 * history entry, so it does not fill the back button; a term changed from
 * elsewhere (Back, a link) shows up in the box.
 */
export function SearchBox({
  id,
  value,
  hrefFor,
  placeholder = "Search tasks…",
}: {
  id: string;
  /** The term in the URL right now. */
  value: string | undefined;
  /** Where the page lives with this term (or none). */
  hrefFor: (search: string | undefined) => string;
  placeholder?: string;
}) {
  const router = useRouter();
  const [search, setSearch] = useState(value ?? "");
  const [synced, setSynced] = useState(value);

  // The URL changed from elsewhere (Back, a link): show its search term.
  if (value !== synced) {
    setSynced(value);
    if ((search.trim() || undefined) !== value) setSearch(value ?? "");
  }

  useEffect(() => {
    const next = search.trim() || undefined;
    if (next === value) return;
    const timer = window.setTimeout(() => {
      router.replace(hrefFor(next), { scroll: false });
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [search, value, hrefFor, router]);

  return (
    <div className="relative min-w-40 flex-1 sm:max-w-64">
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
      />
      <label htmlFor={id} className="sr-only">
        Search tasks
      </label>
      <input
        id={id}
        type="search"
        value={search}
        maxLength={200}
        onChange={(event) => setSearch(event.target.value)}
        placeholder={placeholder}
        className={cn(
          "h-8 w-full rounded-md border border-border bg-card pr-2 pl-8 text-sm shadow-xs",
          "placeholder:text-muted-foreground hover:border-border-strong focus-visible:border-primary",
          "focus-visible:ring-3 focus-visible:ring-primary/20 focus-visible:outline-none",
        )}
      />
    </div>
  );
}

/**
 * One filter as a menu of radio items, with "Any …" on top. While a value is
 * chosen the trigger says so and is tinted, so an active filter is never hidden.
 */
export function FilterMenu<T extends string>({
  label,
  value,
  options,
  labels,
  icon,
  onChange,
  contentClassName,
  anyLabel,
}: {
  label: string;
  value: T | undefined;
  options: readonly T[];
  labels: Record<T, string>;
  icon: (value: T) => ReactNode;
  onChange: (value: T | undefined) => void;
  /** For menus that can grow long, such as a company's people. */
  contentClassName?: string;
  /** The "no filter" item; "Any <label>" unless said otherwise. */
  anyLabel?: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          buttonClasses("secondary", "sm"),
          value && "border-primary/40 bg-primary/5 text-primary hover:bg-primary/10",
        )}
      >
        {value ? icon(value) : <ListFilter aria-hidden="true" />}
        {value ? `${label}: ${labels[value]}` : label}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className={cn("w-48", contentClassName)}>
        <DropdownMenuLabel>Filter by {label.toLowerCase()}</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={value ?? ANY}
          onValueChange={(next) => onChange(next === ANY ? undefined : (next as T))}
        >
          <DropdownMenuRadioItem value={ANY}>
            {anyLabel ?? `Any ${label.toLowerCase()}`}
          </DropdownMenuRadioItem>
          {options.map((option) => (
            <DropdownMenuRadioItem key={option} value={option}>
              {icon(option)}
              {labels[option]}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
