import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { MemberRoleSelect } from "@/features/workspaces/components/member-role-select";
import { RemoveMemberButton } from "@/features/workspaces/components/remove-member-button";
import { formatAccountDate } from "@/features/users/user-utils";
import {
  WORKSPACE_ROLE_BADGES,
  WORKSPACE_ROLE_LABELS,
} from "@/features/workspaces/workspace-utils";
import type { WorkspaceCapability, WorkspaceMember, WorkspaceRole } from "@/types/workspace";

/**
 * A company's people.
 *
 * Which controls appear follows the workspace's `capabilities`, computed by the
 * backend's access policy: `change_roles`, `manage` (remove others) and `leave`.
 * In view mode (a suspended company) none of them is present, so the table is
 * read-only without restating that rule here. The one rule about the *target*
 * --- only an owner removes an owner --- mirrors the service. Each action is still
 * authorized per request (architecture doc 8.2).
 */
export function MemberTable({
  workspaceId,
  members,
  actorId,
  myRole,
  capabilities,
}: {
  workspaceId: string;
  members: WorkspaceMember[];
  actorId: string;
  myRole: WorkspaceRole;
  capabilities: readonly WorkspaceCapability[];
}) {
  if (members.length === 0) {
    return (
      <EmptyState
        title="Nobody is here"
        description="A tenant always has its owner, so this list being empty means the workspace was just opened."
      />
    );
  }

  const mayChangeRoles = capabilities.includes("change_roles");
  const mayRemoveOthers = capabilities.includes("manage");
  const mayLeave = capabilities.includes("leave");

  return (
    // `relative` matters: screen-reader-only labels are absolutely positioned, and
    // only a *positioned* scroll container clips them. Without it they poke out
    // past a phone's edge and the whole page scrolls sideways.
    <div className="relative overflow-x-auto rounded-xl border border-border bg-card shadow-xs">
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
            const mayRemove = isActor
              ? mayLeave
              : mayRemoveOthers && (member.role !== "owner" || myRole === "owner");

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
