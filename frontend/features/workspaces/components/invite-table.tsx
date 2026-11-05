import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { RevokeInviteButton } from "@/features/workspaces/components/revoke-invite-button";
import { formatAccountDate } from "@/features/users/user-utils";
import {
  INVITE_STATUS_BADGES,
  INVITE_STATUS_LABELS,
  WORKSPACE_ROLE_LABELS,
} from "@/features/workspaces/workspace-utils";
import type { WorkspaceInvite } from "@/types/workspace";

/**
 * The company's invitation history.
 *
 * Open offers are listed with the ones already resolved, because an admin who
 * revoked something should be able to see that they did. `canRevoke` comes from
 * the workspace's capabilities: in view mode the history stays visible, but
 * nothing can be withdrawn.
 */
export function InviteTable({
  workspaceId,
  invites,
  canRevoke,
}: {
  workspaceId: string;
  invites: WorkspaceInvite[];
  canRevoke: boolean;
}) {
  if (invites.length === 0) {
    return (
      <EmptyState
        title="No invitations"
        description="Invite a colleague by email address; they accept it from their own profile."
      />
    );
  }

  return (
    // `relative` matters: screen-reader-only labels are absolutely positioned, and
    // only a *positioned* scroll container clips them. Without it they poke out
    // past a phone's edge and the whole page scrolls sideways.
    <div className="relative overflow-x-auto rounded-xl border border-border bg-card shadow-xs">
      <table className="w-full min-w-[30rem] text-left text-sm">
        <caption className="sr-only">
          Invitations for this workspace, the role offered and whether it was taken.
        </caption>
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-3 font-medium">
              Address
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Offered
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Status
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {invites.map((invite) => (
            <tr key={invite.id}>
              <th scope="row" className="max-w-56 truncate px-4 py-3 font-normal text-foreground">
                {invite.email}
              </th>
              <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                {WORKSPACE_ROLE_LABELS[invite.role]}
              </td>
              <td className="px-4 py-3 align-top">
                <Badge variant={INVITE_STATUS_BADGES[invite.status]}>
                  {INVITE_STATUS_LABELS[invite.status]}
                </Badge>
                <span className="ml-2 text-xs text-muted-foreground">
                  {formatAccountDate(
                    invite.status === "pending" ? invite.created_at : invite.resolved_at ?? invite.created_at,
                  )}
                </span>
              </td>
              <td className="px-4 py-3 text-right align-top">
                {canRevoke && invite.status === "pending" ? (
                  <RevokeInviteButton workspaceId={workspaceId} invite={invite} />
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
