import { Badge } from "@/components/ui/badge";
import { CreateWorkspaceForm, WorkspaceList, fetchMyWorkspaces } from "@/features/workspaces";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import type { WorkspaceListResponse } from "@/types/workspace";

export const dynamic = "force-dynamic";

export const metadata = { title: "Workspaces" };

/**
 * The tenants the caller belongs to.
 *
 * Every account has at least one: registration creates a private workspace, so
 * this list is never empty and the "individual or company" question is answered
 * by the kind column rather than by two different code paths
 * (architecture doc section 5).
 */
export default async function WorkspacesPage() {
  const cookie = await getServerCookieHeader();

  let teams: WorkspaceListResponse | null = null;
  let loadError: string | null = null;
  try {
    teams = await fetchMyWorkspaces({ page_size: 50 }, cookie);
  } catch (error) {
    loadError = error instanceof Error ? error.message : "Workspaces could not be loaded.";
  }

  return (
    <div className="grid gap-8 md:grid-cols-[minmax(0,1fr)_20rem]">
      <section aria-labelledby="workspaces-heading" className="min-w-0">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <h1 id="workspaces-heading" className="text-xl font-semibold tracking-tight">
            Workspaces
          </h1>
          {teams ? <Badge variant="neutral">{teams.total} total</Badge> : null}
        </div>

        {loadError ? (
          <div
            role="alert"
            className="rounded-xl border border-danger/40 bg-danger/10 p-5 text-sm text-danger"
          >
            <p className="font-medium">Workspaces could not be loaded.</p>
            <p className="mt-1 text-xs">{loadError}</p>
          </div>
        ) : teams ? (
          <WorkspaceList teams={teams.items} />
        ) : null}
      </section>

      <aside className="md:sticky md:top-20 md:self-start">
        <CreateWorkspaceForm />
      </aside>
    </div>
  );
}
