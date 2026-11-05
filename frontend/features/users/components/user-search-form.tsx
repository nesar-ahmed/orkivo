import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface UserSearchFormProps {
  readonly search?: string;
  /** Where the form submits to, so it can serve any directory listing. */
  readonly basePath: string;
  readonly label?: string;
}

/**
 * Directory search.
 *
 * A plain `GET` form: the page reads `?search=` server-side, so filtering works
 * without a client component, keeps the URL shareable, and survives JavaScript
 * being unavailable.
 */
export function UserSearchForm({
  search,
  basePath,
  label = "Search accounts by email or display name",
}: UserSearchFormProps) {
  return (
    <form action={basePath} method="get" className="flex flex-wrap items-center gap-2">
      <div>
        <label htmlFor="account-search" className="sr-only">
          {label}
        </label>
        <Input
          id="account-search"
          name="search"
          type="search"
          defaultValue={search ?? ""}
          maxLength={200}
          placeholder="Email or display name"
          className="w-64"
        />
      </div>

      <Button type="submit" variant="secondary">
        Search
      </Button>

      {search ? (
        <Link
          href={basePath}
          className="text-xs font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          Clear
        </Link>
      ) : null}
    </form>
  );
}
