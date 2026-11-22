"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { CornerDownLeft, FileText, FolderKanban, Loader2, Search } from "lucide-react";
import { Dialog as Primitive } from "radix-ui";
import { Kbd } from "@/components/ui/kbd";
import { searchEverywhere } from "@/features/command-palette/api/search-queries";
import {
  GROUP_LABELS,
  matchesQuery,
  pageItems,
  recentItems,
  searchItems,
  workspaceItems,
  type PaletteGroup,
  type PaletteItem,
} from "@/features/command-palette/palette-items";
import { readRecent, rememberRecent } from "@/features/command-palette/recent-items";
import { StatusIcon } from "@/features/tasks/components/task-icons";
import { WorkspaceMark } from "@/features/workspaces/components/workspace-switcher";
import { findWorkspaceForPath } from "@/features/workspaces/workspace-utils";
import { cn } from "@/lib/utils/cn";
import type { User } from "@/types/auth";
import type { SearchResponse } from "@/types/search";
import type { Workspace } from "@/types/workspace";

/** How long typing pauses before the palette asks the API. */
const SEARCH_DEBOUNCE_MS = 150;

const GROUP_ORDER: readonly PaletteGroup[] = ["recent", "pages", "tasks", "projects", "workspaces"];

/**
 * Jump to any task, project, workspace or page: Ctrl+K (⌘K on a Mac) from
 * anywhere in the product, or the search button in the top bar.
 *
 * The pattern Linear, GitHub, Slack and VS Code made standard: one box, results
 * grouped by kind, arrows to move, Enter to open, Escape to leave. Before anything
 * is typed it offers what the person opened recently, the pages of the workspace
 * they are in, and their workspaces. As they type, pages are filtered here and
 * everything else is asked of the API, which only ever searches workspaces the
 * person may read --- so the palette can never surface another company's work.
 *
 * Accessible as a combobox (WAI-ARIA 1.2): focus stays in the box, the active
 * option is announced through `aria-activedescendant`, and every group is named.
 */
export function CommandPalette({
  user,
  workspaces,
}: {
  user: User;
  workspaces: readonly Workspace[] | null;
}) {
  const [open, setOpen] = useState(false);
  const modifier = useModifierKeyLabel();

  useEffect(() => {
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <Primitive.Root open={open} onOpenChange={setOpen}>
      <Primitive.Trigger
        className={cn(
          "flex h-8 items-center gap-2 rounded-md border border-border bg-card px-2.5 text-sm text-muted-foreground shadow-xs",
          "transition-colors hover:border-border-strong hover:text-foreground sm:w-56",
        )}
      >
        <Search aria-hidden="true" className="size-4" />
        <span className="hidden flex-1 text-left sm:inline">Search…</span>
        <span className="sr-only sm:hidden">Search</span>
        <span className="hidden items-center gap-0.5 sm:flex" aria-hidden="true">
          <Kbd>{modifier}</Kbd>
          <Kbd>K</Kbd>
        </span>
      </Primitive.Trigger>
      {open ? (
        <PaletteDialog user={user} workspaces={workspaces ?? []} onClose={() => setOpen(false)} />
      ) : null}
    </Primitive.Root>
  );
}

const noSubscription = () => () => {};

/**
 * "⌘" on a Mac and "Ctrl" elsewhere, for the shortcut hint. The server cannot
 * know, so it renders "Ctrl" and a Mac switches after hydration --- the hand-over
 * `useSyncExternalStore` supports without a mismatch, as `useToday` does.
 */
function useModifierKeyLabel(): string {
  return useSyncExternalStore(
    noSubscription,
    () => (/Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl"),
    () => "Ctrl",
  );
}

/**
 * The open palette. Mounted only while open, so every opening starts from an
 * empty box and fresh recent items.
 */
function PaletteDialog({
  user,
  workspaces,
  onClose,
}: {
  user: User;
  workspaces: readonly Workspace[];
  onClose: () => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const listId = useId();
  const listRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<{ term: string; results: SearchResponse } | null>(null);
  const [failedTerm, setFailedTerm] = useState<string | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [recent] = useState(() =>
    readRecent(user.id, new Set(workspaces.map((workspace) => workspace.id))),
  );

  const term = query.trim();
  const current = findWorkspaceForPath(pathname, workspaces) ?? null;

  // Ask the API once typing pauses; a newer question cancels the older one.
  useEffect(() => {
    if (!term) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      searchEverywhere(term, controller.signal)
        .then((results) => setFound({ term, results }))
        .catch(() => {
          if (!controller.signal.aborted) setFailedTerm(term);
        });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [term]);

  const pages = pageItems(current, user);
  const items: PaletteItem[] = term
    ? [
        ...pages.filter((item) => matchesQuery(item, term)),
        ...(found?.term === term ? searchItems(found.results) : []),
      ]
    : [...recentItems(recent), ...pages, ...workspaceItems(workspaces)];
  const searching = term !== "" && found?.term !== term && failedTerm !== term;
  const active = items.find((item) => item.key === activeKey) ?? items[0] ?? null;
  const optionId = (item: PaletteItem) => `${listId}-${item.key.replace(/[^\w-]/g, "_")}`;

  // Keep the active option in view as the arrows move it --- inside the list only.
  useEffect(() => {
    if (!active) return;
    const option = document.getElementById(optionId(active));
    const list = listRef.current;
    if (!option || !list) return;
    if (option.offsetTop < list.scrollTop) list.scrollTop = option.offsetTop - 8;
    else if (option.offsetTop + option.offsetHeight > list.scrollTop + list.clientHeight) {
      list.scrollTop = option.offsetTop + option.offsetHeight - list.clientHeight + 8;
    }
  });

  function openItem(item: PaletteItem) {
    if (item.recent) rememberRecent(user.id, item.recent);
    onClose();
    router.push(item.href);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (items.length === 0) return;
    const index = active ? items.indexOf(active) : -1;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActiveKey(items[(index + step + items.length) % items.length]!.key);
    } else if (event.key === "Enter" && active) {
      event.preventDefault();
      openItem(active);
    }
  }

  const groups = GROUP_ORDER.map((group) => ({
    group,
    items: items.filter((item) => item.group === group),
  })).filter((entry) => entry.items.length > 0);

  return (
    <Primitive.Portal>
      <Primitive.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px] animate-fade-in" />
      <Primitive.Content
        aria-describedby={undefined}
        className={cn(
          "fixed top-4 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 flex-col overflow-hidden",
          "max-h-[calc(100dvh-2rem)] rounded-xl border border-border bg-popover text-popover-foreground shadow-lg",
          "animate-pop-in focus:outline-none sm:top-[12vh] sm:max-h-[70vh]",
        )}
      >
        <Primitive.Title className="sr-only">Search Orkivo</Primitive.Title>
        <div className="flex items-center gap-2 border-b border-border px-3">
          {searching ? (
            <Loader2 aria-hidden="true" className="size-4 shrink-0 animate-spin text-muted-foreground" />
          ) : (
            <Search aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
          )}
          <input
            autoFocus
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={active ? optionId(active) : undefined}
            aria-label="Search tasks, projects, workspaces and pages"
            placeholder="Search tasks, projects, workspaces…"
            value={query}
            maxLength={200}
            onChange={(event) => {
              setQuery(event.target.value);
              setActiveKey(null);
            }}
            onKeyDown={handleKeyDown}
            className="h-12 min-w-0 flex-1 bg-transparent text-sm placeholder:text-muted-foreground focus:outline-none"
          />
          <Kbd className="hidden sm:inline-flex">Esc</Kbd>
        </div>

        <div ref={listRef} id={listId} role="listbox" aria-label="Results" className="relative overflow-y-auto p-2">
          {groups.map(({ group, items: members }) => {
            const headingId = `${listId}-${group}`;
            return (
              <div key={group} role="group" aria-labelledby={headingId} className="pb-2 last:pb-0">
                <div
                  id={headingId}
                  role="presentation"
                  className="px-2 pt-1 pb-1.5 text-[0.7rem] font-medium tracking-wide text-muted-foreground uppercase"
                >
                  {GROUP_LABELS[group]}
                </div>
                {members.map((item) => {
                  const selected = item.key === active?.key;
                  return (
                    <div
                      key={item.key}
                      id={optionId(item)}
                      role="option"
                      aria-selected={selected}
                      onMouseMove={() => setActiveKey(item.key)}
                      // Pressed, not clicked: the input keeps focus, as a combobox's should.
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => openItem(item)}
                      className={cn(
                        "flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-2 text-sm",
                        selected ? "bg-muted text-foreground" : "text-popover-foreground",
                      )}
                    >
                      <ItemIcon item={item} />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {item.detail ? (
                        <span className="max-w-[45%] shrink-0 truncate text-xs text-muted-foreground">
                          {item.detail}
                        </span>
                      ) : null}
                      {selected ? (
                        <CornerDownLeft aria-hidden="true" className="size-3.5 shrink-0 text-muted-foreground" />
                      ) : null}
                    </div>
                  );
                })}
              </div>
            );
          })}
          <p aria-live="polite" className={groups.length === 0 ? "px-2 py-6 text-center text-sm text-muted-foreground" : "sr-only"}>
            {statusLine({ term, searching, failed: failedTerm === term, count: items.length })}
          </p>
        </div>

        <footer className="hidden items-center gap-3 border-t border-border px-3 py-2 text-xs text-muted-foreground sm:flex">
          <span className="flex items-center gap-1">
            <Kbd>↑</Kbd>
            <Kbd>↓</Kbd> to move
          </span>
          <span className="flex items-center gap-1">
            <Kbd>Enter</Kbd> to open
          </span>
          <span className="ml-auto">Only workspaces you are in are searched.</span>
        </footer>
      </Primitive.Content>
    </Primitive.Portal>
  );
}

/** What the list says, to everyone when it is empty and to screen readers always. */
function statusLine({
  term,
  searching,
  failed,
  count,
}: {
  term: string;
  searching: boolean;
  failed: boolean;
  count: number;
}): string {
  if (!term) return `${count} suggestions.`;
  if (failed) return "Search is not available right now. Pages can still be opened.";
  if (searching) return "Searching…";
  return count === 0 ? `Nothing matches “${term}”.` : `${count} results.`;
}

function ItemIcon({ item }: { item: PaletteItem }): ReactNode {
  if (item.kind === "task" && item.status) return <StatusIcon status={item.status} />;
  if (item.kind === "project") {
    return <FolderKanban aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />;
  }
  if (item.kind === "workspace" && item.workspace) {
    return <WorkspaceMark workspace={item.workspace} className="size-4 rounded text-[0.6rem]" />;
  }
  return <FileText aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />;
}
