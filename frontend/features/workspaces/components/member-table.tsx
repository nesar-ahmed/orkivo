import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { MemberRoleSelect } from "@/features/workspaces/components/member-role-select";
import { RemoveMemberButton } from "@/features/workspaces/components/remove-member-button";
import { formatAccountDate } from "@/features/users/user-utils";
import {
  WORKSPACE_ROLE_BADGES,
  WORKSPACE_ROLE_LABELS,
} from "@/features/workspaces/workspace-utils";
import type { WorkspaceMember, WorkspaceRole } from "@/types/workspace";

/**
 * A company's people.
 *
 * Which controls appear follows what the API will accept: role changes are an
 * owner&rsquo;s act, an admin may remove members but not the owner, and anyone may
 * leave. That is presentation, not permission --- each action is still authorized
 * per request (architecture doc 8.2).
 */
export function MemberTable({
  workspaceId,
  members,
  actorId,
  myRole,
}: {
  workspaceId: string;
  members: WorkspaceMember[];
  actorId: string;
  myRole: WorkspaceRole;
}) {
  if (members.length === 0) {
    return (
      <EmptyState
        title="Nobody is here"
        description="A tenant always has its owner, so this list being empty means the workspace was just opened."
      />
    );
  }

  const mayChangeRoles = myRole === "owner";

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
      <table className="w-full min-w-[36rem] text-left text-sm">
        <caption className="sr-only">
          Members of this workspace, their role in it, and when they joined.
        </caption>
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-3 font-medium">
              Person
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Role
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Joined
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {members.map((member) => {
            const isActor = member.user_id === actorId;
            const mayRemove =
              isActor ||
              (mayChangeRoles && !isActor) ||
              (myRole === "admin" && member.role !== "owner" && !isActor);

            return (
              <tr key={member.id}>
                <th scope="row" className="max-w-60 px-4 py-3 font-normal">
                  <span className="block truncate font-medium text-foreground">
                    {member.display_name}
                    {isActor ? (
                      <span className="ml-2 text-xs font-normal text-muted-foreground">
                        (you)
                      </span>
                    ) : null}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {member.email}
                  </span>
                </th>
                <td className="px-4 py-3 align-top">
                  {mayChangeRoles && !isActor ? (
                    <MemberRoleSelect workspaceId={workspaceId} member={member} />
                  ) : (
                    <Badge variant={WORKSPACE_ROLE_BADGES[member.role]}>
                      {WORKSPACE_ROLE_LABELS[member.role]}
                    </Badge>
                  )}
                </td>
                <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                  {formatAccountDate(member.joined_at)}
                </td>
                <td className="px-4 py-3 text-right align-top">
                  {mayRemove ? (
                    <RemoveMemberButton
                      workspaceId={workspaceId}
                      member={member}
                      isActor={isActor}
                    />
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
