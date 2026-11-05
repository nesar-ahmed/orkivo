import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { PlatformNav } from "@/components/layout/platform-nav";
import { readCurrentUserOnce } from "@/features/auth";
import {
  AccountTable,
  DirectoryPagination,
  UserSearchForm,
  fetchUsers,
} from "@/features/users";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import type { User, UserListResponse } from "@/types/auth";

export const dynamic = "force-dynamic";

export const metadata = { title: "Accounts" };

const PAGE_SIZE = 20;
const BASE_PATH = "/app/platform/accounts";

interface PageProps {
  searchParams: Promise<{ search?: string; page?: string }>;
}

/**
 * The platform account directory, for operators.
 *
 * This is the surface that existed before tenancy, when &ldquo;admin&rdquo; meant
 * everything. It now covers the platform axis only: accounts and their platform
 * role. Company rosters live with the company, and an operator has no route from
 * here into a tenant&rsquo;s work (architecture doc section 5).
 */
export default async function PlatformAccountsPage({ searchParams }: PageProps) {
  const { search: rawSearch, page: rawPage } = await searchParams;
  const search = rawSearch?.trim() ? rawSearch.trim().slice(0, 200) : undefined;
  const page = clampPage(rawPage);
  const cookie = await getServerCookieHeader();

  let actor: User;
  let directory: UserListResponse;
  try {
    [actor, directory] = await Promise.all([
      readCurrentUserOnce(cookie),
      fetchUsers({ search, page, page_size: PAGE_SIZE }, cookie),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) return <NotForMembers />;
    throw error;
  }

  return (
    <section aria-labelledby="accounts-heading" className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 id="accounts-heading" className="text-xl font-semibold tracking-tight">
          Accounts
        </h1>
        <Badge variant="info">Operators only</Badge>
        <span className="ml-auto">
          <PlatformNav />
        </span>
      </div>

      <p className="max-w-2xl text-xs text-muted-foreground">
        A platform role decides who may run Orkivo&rsquo;s console. It grants no sight of
        anyone&rsquo;s tasks, projects or comments, and no membership in any company.
      </p>

      <UserSearchForm search={search} basePath={BASE_PATH} />

      <AccountTable accounts={directory.items} actorId={actor.id} />

      <DirectoryPagination
        page={directory.page}
        pages={directory.pages}
        total={directory.total}
        search={search}
        basePath={BASE_PATH}
        noun="accounts"
      />
    </section>
  );
}

/** Where an ordinary account belongs when it opens a console URL. */
function NotForMembers() {
  return (
    <section aria-labelledby="accounts-heading">
      <h1 id="accounts-heading" className="mb-4 text-xl font-semibold tracking-tight">
        Accounts
      </h1>
      <EmptyState
        title="Operators only"
        description="The API refused this directory for your account. A platform role is granted by an existing operator, never requested here."
      >
        <Link
          href="/app/dashboard"
          className={cn(
            "inline-flex h-8 items-center justify-center rounded-md border border-border",
            "bg-card px-3 text-sm font-medium text-card-foreground hover:bg-muted",
          )}
        >
          Back to tasks
        </Link>
      </EmptyState>
    </section>
  );
}

/** A hand-typed ``?page=`` must not become a 422 or an empty table. */
function clampPage(value: string | undefined): number {
  const parsed = Number(value ?? 1);
  if (!Number.isInteger(parsed)) return 1;
  return Math.min(Math.max(parsed, 1), 10_000);
}
