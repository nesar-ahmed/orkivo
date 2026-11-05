import type { Metadata } from "next";
import { Pagination } from "@/components/ui/pagination";
import { readCurrentUserOnce } from "@/features/auth";
import {
  InviteForm,
  InviteTable,
  MemberTable,
  fetchInvites,
  fetchMembers,
  hasCapability,
  workspacePath,
} from "@/features/workspaces";
import { parsePageParam } from "@/lib/utils/page-param";
import { loadCompany } from "../load-company";

export const dynamic = "force-dynamic";

const MEMBERS_PER_PAGE = 25;
const INVITES_PER_PAGE = 25;

interface PageProps {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string; invites_page?: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { workspace } = await loadCompany(params);
  return { title: `${workspace.name} · People` };
}

/**
 * A company&rsquo;s people: who is in, what they may do, and which offers are open.
 *
 * Each read is authorized on its own. What is shown and offered follows the
 * workspace&rsquo;s capabilities from the backend&rsquo;s access policy: the
 * invitation history needs `view_invites`, the invite form `invite`, and the
 * member controls `change_roles` / `manage` / `leave`. In view mode (a suspended
 * company) everything stays visible and nothing can be changed.
 *
 * Both lists page independently (`?page=` and `?invites_page=`), so a large
 * company never hides anyone past an arbitrary cut-off.
 */
export default async function CompanyPeoplePage({ params, searchParams }: PageProps) {
  const { workspace, cookie } = await loadCompany(params);
  const query = await searchParams;
  const memberPage = parsePageParam(query.page);
  const invitePage = parsePageParam(query.invites_page);

  const canViewInvites = hasCapability(workspace, "view_invites");
  const canInvite = hasCapability(workspace, "invite");
  const canManage = hasCapability(workspace, "manage");
  const [actor, members, invites] = await Promise.all([
    readCurrentUserOnce(cookie),
    fetchMembers(workspace.id, { page: memberPage, page_size: MEMBERS_PER_PAGE }, cookie),
    canViewInvites
      ? fetchInvites(workspace.id, { page: invitePage, page_size: INVITES_PER_PAGE }, cookie)
      : Promise.resolve(null),
  ]);
  const basePath = workspacePath(workspace, "people");

  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="members-heading" className="flex flex-col gap-3">
        <h2 id="members-heading" className="text-sm font-semibold text-card-foreground">
          People · {members.total}
        </h2>
        <MemberTable
          workspaceId={workspace.id}
          members={members.items}
          actorId={actor.id}
          myRole={workspace.my_role}
          capabilities={workspace.capabilities}
        />
        <Pagination
          page={members.page}
          pages={members.pages}
          total={members.total}
          basePath={basePath}
          noun="people"
          singular="person"
          params={{ invites_page: query.invites_page }}
        />
      </section>

      {invites ? (
        <section
          aria-labelledby="invitations-heading"
          // An explicit shrinkable column: an implicit `auto` one grows to the
          // invitation table's minimum width and pushes the page sideways on phones.
          className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]"
        >
          <h2 id="invitations-heading" className="sr-only">
            Invitations
          </h2>
          {canInvite ? (
            <InviteForm workspaceId={workspace.id} />
          ) : (
            <p className="rounded-xl border border-border bg-card p-5 text-xs text-muted-foreground shadow-sm">
              {workspace.status === "suspended"
                ? "View mode: invitations can be seen but not sent or withdrawn while this company is suspended."
                : "Your role does not allow inviting people."}
            </p>
          )}
          <div className="flex flex-col gap-3">
            <p className="text-sm font-semibold text-card-foreground">Offers · {invites.total}</p>
            <InviteTable workspaceId={workspace.id} invites={invites.items} canRevoke={canManage} />
            <Pagination
              page={invites.page}
              pages={invites.pages}
              total={invites.total}
              basePath={basePath}
              noun="offers"
              pageParam="invites_page"
              params={{ page: query.page }}
            />
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
