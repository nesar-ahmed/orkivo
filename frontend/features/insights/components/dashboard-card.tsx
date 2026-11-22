import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils/cn";

/**
 * One card of a dashboard: a titled region, with an optional way out to the
 * full page it summarises ("See all"). Every card is a landmark with its own
 * heading, so a screen-reader user can jump between them.
 */
export function DashboardCard({
  id,
  title,
  description,
  action,
  className,
  children,
}: {
  /** Unique on the page; names the region by its heading. */
  id: string;
  title: string;
  description?: string;
  action?: { href: string; label: string };
  className?: string;
  children: ReactNode;
}) {
  const headingId = `${id}-heading`;
  return (
    <section
      aria-labelledby={headingId}
      className={cn(
        "flex min-w-0 flex-col gap-4 rounded-xl border border-border bg-card p-4 shadow-xs sm:p-5",
        className,
      )}
    >
      <header className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 id={headingId} className="text-sm font-semibold text-card-foreground">
            {title}
          </h3>
          {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
        </div>
        {action ? (
          <Link
            href={action.href}
            className="inline-flex shrink-0 items-center gap-1 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            {action.label}
            <ArrowRight aria-hidden="true" className="size-3.5" />
          </Link>
        ) : null}
      </header>
      {children}
    </section>
  );
}

/** What a card shows when its part of the dashboard could not be read. */
export function CardLoadError({ what }: { what: string }) {
  return (
    <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-xs text-danger">
      {what} could not be loaded. Reload the page to try again.
    </p>
  );
}
