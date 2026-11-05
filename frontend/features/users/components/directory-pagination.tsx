import Link from "next/link";
import { cn } from "@/lib/utils/cn";

interface DirectoryPaginationProps {
  readonly page: number;
  readonly pages: number;
  readonly total: number;
  readonly search?: string;
  /** The listing being paged, so the control serves any directory. */
  readonly basePath: string;
  readonly noun?: string;
  /** Extra query keys to carry through, such as a tenant filter. */
  readonly params?: Record<string, string | undefined>;
}

const linkStyles =
  "inline-flex h-8 items-center rounded-md border border-border bg-card px-3 text-xs " +
  "font-medium text-card-foreground hover:bg-muted";

/**
 * Page controls for a server-rendered directory.
 *
 * Links rather than buttons: the page reads the query string, so a plain href is
 * what makes paging work, and the active search carries along.
 */
export function DirectoryPagination({
  page,
  pages,
  total,
  search,
  basePath,
  noun = "accounts",
  params,
}: DirectoryPaginationProps) {
  const summary = `${total} ${total === 1 ? noun.replace(/s$/, "") : noun}`;
  if (pages <= 1) {
    return <p className="text-xs text-muted-foreground">{summary}</p>;
  }

  const hrefFor = (target: number) => {
    const query = new URLSearchParams();
    if (search) query.set("search", search);
    for (const [key, value] of Object.entries(params ?? {})) {
      if (value) query.set(key, value);
    }
    query.set("page", String(target));
    return `${basePath}?${query.toString()}`;
  };

  return (
    <nav aria-label={`${noun} pages`} className="flex items-center gap-3">
      <p className="text-xs text-muted-foreground">
        {summary} · page {page} of {pages}
      </p>
      <div className="flex items-center gap-2">
        {page > 1 ? (
          <Link href={hrefFor(page - 1)} className={linkStyles}>
            Previous
          </Link>
        ) : (
          <span aria-disabled="true" className={cn(linkStyles, "pointer-events-none opacity-50")}>
            Previous
          </span>
        )}
        {page < pages ? (
          <Link href={hrefFor(page + 1)} className={linkStyles}>
            Next
          </Link>
        ) : (
          <span aria-disabled="true" className={cn(linkStyles, "pointer-events-none opacity-50")}>
            Next
          </span>
        )}
      </div>
    </nav>
  );
}
