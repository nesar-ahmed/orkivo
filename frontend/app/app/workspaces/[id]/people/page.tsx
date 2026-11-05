import Link from "next/link";
import { notFound } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { readCurrentUserOnce } from "@/features/auth";
import {
  InviteForm,
  InviteTable,
  MemberTable,
  fetchInvites,
  fetchMembers,
  fetchWorkspace,
} from "@/features/workspaces";
import { WORKSPACE_KIND_LABELS } from "@/features/workspaces/workspace-utils";
import { ApiError } from "@/lib/api/client";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import type { Workspace } from "@/types/workspace";

export const dynamic = "force-dynamic";

export const metadata = { title: "People" };

interface PageProps {
  params: Promise<{ id: string }>;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * A company&rsquo;s people: who is in, what they may do, and which offers are open.
 *
 * Each read is authorized on its own, and the invitation panel is fetched only
 * when the caller&rsquo;s role can read it. A tenant the caller is not in answers
 * &ldquo;not found&rdquo;, and that is shown as a missing page rather than a permission
 * error --- the API refuses to distinguish the two, and this screen does not
 * invent a distinction (architecture doc 8.2, section 9).
 */
export default async function WorkspacePeoplePage({ params }: PageProps) {
  const { id: workspaceId } = await params;
  // A hand-typed address should read as "no such company", not as a 422.
  if (!UUID_PATTERN.test(workspaceId)) notFound();

  const cookie = await getServerCookieHeader();

  let workspace: Workspace;
  try {
    workspace = await fetchWorkspace(workspaceId, cookie);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 403)) notFound();
    throw error;
  }

  const canManage = workspace.my_role === "owner" || workspace.my_role === "admin";
  const [actor, members, invites] = await Promise.all([
    readCurrentUserOnce(cookie),
    fetchMembers(workspaceId, { page_size: 100 }, cookie),
    canManage
      ? fetchInvites(workspaceId, { page_size: 100 }, cookie)
      : Promise.resolve(null),
  ]);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 id="people-heading" className="text-xl font-semibold tracking-tight">
          {workspace.name}
        </h1>
        <Badge variant="neutral">{WORKSPACE_KIND_LABELS[workspace.kind]}</Badge>
        <Badge variant={workspace.my_role === "owner" ? "primary" : "info"}>
          You are {workspace.my_role}
        </Badge>
        {workspace.slug ? (
          <span className="font-mono text-xs text-muted-foreground">/{workspace.slug}</span>
        ) : null}
        <Link
          href="/app/workspaces"
          className="ml-auto text-xs font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          All workspaces
        </Link>
      </header>

      <section aria-labelledby="members-heading" className="flex flex-col gap-3">
        <h2 id="members-heading" className="text-sm font-semibold text-card-foreground">
          People · {members.total}
        </h2>
        <MemberTable
          workspaceId={workspace.id}
          members={members.items}
          actorId={actor.id}
          myRole={workspace.my_role}
        />
      </section>

      {workspace.kind !== "team" ? (
        <p className="text-xs text-muted-foreground">
          A private workspace holds only its owner, so there is no one to invite.
        </p>
      ) : canManage ? (
        <section
          aria-labelledby="invitations-heading"
          className="grid gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]"
        >
          <h2 id="invitations-heading" className="sr-only">
            Invitations
          </h2>
          <InviteForm workspaceId={workspace.id} />
          <div className="flex flex-col gap-3">
            <p className="text-sm font-semibold text-card-foreground">
              Offers · {invites?.items.length ?? 0}
            </p>
            <InviteTable workspaceId={workspace.id} invites={invites?.items ?? []} />
          </div>
        </section>
      ) : (
        <p className="text-xs text-muted-foreground">
          Only an owner or admin can invite people or see the open offers.
        </p>
      )}
    </div>
  );
}
