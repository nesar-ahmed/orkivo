import type { ReactNode } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils/cn";

export interface StatTile {
  readonly key: string;
  readonly label: string;
  readonly value: number;
  /** The list this number counts. */
  readonly href: string;
  readonly icon: ReactNode;
  /** A short line under the number: "of 24 tasks", "62% of all work". */
  readonly hint?: string;
  /** `attention` tints the tile when the number is not zero (overdue work). */
  readonly tone?: "neutral" | "attention";
}

/**
 * The dashboard's headline numbers, each a link to exactly the tasks it counts.
 *
 * Big, scannable and few --- the pattern every work tool's summary opens with ---
 * so "is anything on fire?" is answered before anything else is read. A tile
 * that needs attention says so with color *and* with its label, never color
 * alone.
 */
export function StatTiles({ tiles, label }: { tiles: readonly StatTile[]; label: string }) {
  return (
    <ul aria-label={label} className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {tiles.map((tile) => {
        const alarming = tile.tone === "attention" && tile.value > 0;
        return (
          <li key={tile.key} className="min-w-0">
            <Link
              href={tile.href}
              className={cn(
                "flex h-full flex-col gap-1 rounded-xl border bg-card p-4 shadow-xs transition-colors",
                "hover:border-border-strong hover:bg-muted/40",
                alarming ? "border-danger/40 bg-danger/5" : "border-border",
              )}
            >
              <span
                className={cn(
                  "flex items-center gap-1.5 text-xs font-medium [&_svg]:size-3.5 [&_svg]:shrink-0",
                  alarming ? "text-danger" : "text-muted-foreground",
                )}
              >
                {tile.icon}
                <span className="truncate">{tile.label}</span>
              </span>
              <span
                className={cn(
                  "text-2xl font-semibold tracking-tight tabular-nums",
                  alarming ? "text-danger" : "text-card-foreground",
                )}
              >
                {tile.value}
              </span>
              {tile.hint ? (
                <span className="truncate text-xs text-muted-foreground">{tile.hint}</span>
              ) : null}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
