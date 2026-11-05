import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { PlatformNav } from "@/components/layout/platform-nav";
import { DirectoryPagination, UserSearchForm } from "@/features/users";
import { TenantTable, fetchTenants } from "@/features/workspaces";
import { WORKSPACE_KIND_LABELS } from "@/features/workspaces/workspace-utils";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import type { TenantListResponse, WorkspaceKind } from "@/types/workspace";

export const dynamic = "force-dynamic";

export const metadata = { title: "Tenants" };

const PAGE_SIZE = 20;
const BASE_PATH = "/app/platform/tenants";
const KINDS: WorkspaceKind[] = ["team", "personal"];

interface PageProps {
  searchParams: Promise<{ search?: string; kind?: string; page?: string }>;
}

/**
 * The platform console: every tenant, as lifecycle and head counts.
 *
 * The privacy line is drawn by the response rather than by restraint on this
 * page: there is no link from here into a tenant&rsquo;s tasks, because the API
 * offers an operator no such read (architecture doc section 9).
 */
export default async function PlatformTenantsPage({ searchParams }: PageProps) {
  const { search: rawSearch, kind: rawKind, page: rawPage } = await searchParams;
  const search = rawSearch?.trim() ? rawSearch.trim().slice(0, 200) : undefined;
  const kind = KINDS.includes(rawKind as WorkspaceKind) ? (rawKind as WorkspaceKind) : undefined;
  const page = clampPage(rawPage);
  const cookie = await getServerCookieHeader();

  let tenants: TenantListResponse;
  try {
    tenants = await fetchTenants({ search, kind, page, page_size: PAGE_SIZE }, cookie);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) return <NotForMembers />;
    throw error;
  }

  return (
    <section aria-labelledby="tenants-heading" className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 id="tenants-heading" className="text-xl font-semibold tracking-tight">
          Tenants
        </h1>
        <Badge variant="info">Operators only</Badge>
        <span className="ml-auto">
          <PlatformNav />
        </span>
      </div>

      <p className="max-w-2xl text-xs text-muted-foreground">
        Suspending stops a company admitting new members and is reversible; it deletes nothing.
        Content belongs to the tenant, and no part of this console reads it.
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <UserSearchForm
          search={search}
          basePath={BASE_PATH}
          label="Search tenants by name or address"
        />
        <div className="flex items-center gap-1 text-xs" role="group" aria-label="Filter by kind">
          <KindFilter label="All kinds" kind={undefined} activeKind={kind} search={search} />
          {KINDS.map((value) => (
            <KindFilter
              key={value}
              label={WORKSPACE_KIND_LABELS[value]}
              kind={value}
              activeKind={kind}
              search={search}
            />
          ))}
        </div>
      </div>

      <TenantTable tenants={tenants.items} />

      <DirectoryPagination
        page={tenants.page}
        pages={tenants.pages}
        total={tenants.total}
        search={search}
        basePath={BASE_PATH}
        noun="tenants"
        params={{ kind }}
      />
    </section>
  );
}

/** One kind filter, keeping whatever else is in the query string. */
function KindFilter({
  label,
  kind,
  activeKind,
  search,
}: {
  label: string;
  kind?: WorkspaceKind;
  activeKind?: WorkspaceKind;
  search?: string;
}) {
  const query = new URLSearchParams();
  if (search) query.set("search", search);
  if (kind) query.set("kind", kind);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";

  return (
    <Link
      href={`${BASE_PATH}${suffix}`}
      aria-pressed={kind === activeKind}
      className={cn(
        "rounded-md border px-2.5 py-1 font-medium",
        kind === activeKind
          ? "border-primary bg-primary/10 text-primary"
          : "border-border text-muted-foreground hover:bg-muted",
      )}
    >
      {label}
    </Link>
  );
}

/** Where an ordinary account belongs when it opens a console URL. */
function NotForMembers() {
  return (
    <section aria-labelledby="tenants-heading">
      <h1 id="tenants-heading" className="mb-4 text-xl font-semibold tracking-tight">
        Tenants
      </h1>
      <EmptyState
        title="Operators only"
        description="The platform console is refused for your account. Your own workspaces are listed under Workspaces."
      >
        <Link
          href="/app/workspaces"
          className={cn(
            "inline-flex h-8 items-center justify-center rounded-md border border-border",
            "bg-card px-3 text-sm font-medium text-card-foreground hover:bg-muted",
          )}
        >
          Your workspaces
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
