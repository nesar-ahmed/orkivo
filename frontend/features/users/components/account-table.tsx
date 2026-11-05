import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { AccountStatusAction } from "@/features/users/components/account-status-action";
import { PlatformRoleSelect } from "@/features/users/components/platform-role-select";
import {
  PLATFORM_ROLE_BADGES,
  PLATFORM_ROLE_LABELS,
  formatAccountDate,
} from "@/features/users/user-utils";
import type { AccountAdmin } from "@/types/auth";

/**
 * The platform account directory, for operators.
 *
 * This is the one list that is *not* tenant-scoped: it exists so someone can run
 * the platform, and it exposes accounts, not their work. Company rosters live on
 * the workspace people screen (architecture doc section 5).
 *
 * The status column is where an individual is stopped: disabling an account ends
 * its sessions and blocks sign-in, and is the platform's lever for a person.
 */
export function AccountTable({
  accounts,
  actorId,
}: {
  accounts: AccountAdmin[];
  actorId: string;
}) {
  if (accounts.length === 0) {
    return (
      <EmptyState
        title="No accounts match"
        description="Try a different search term, or clear it to see everyone."
      />
    );
  }

  return (
    // `relative` matters: screen-reader-only labels are absolutely positioned, and
    // only a *positioned* scroll container clips them. Without it they poke out
    // past a phone's edge and the whole page scrolls sideways.
    <div className="relative overflow-x-auto rounded-xl border border-border bg-card shadow-xs">
      <table className="w-full min-w-[44rem] text-left text-sm">
        <caption className="sr-only">
          Platform accounts, with each one&rsquo;s platform role, status and when it registered.
        </caption>
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-3 font-medium">
              Account
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Platform role
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Status
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Registered
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {accounts.map((account) => {
            const isActor = account.id === actorId;
            return (
              <tr key={account.id}>
                <th scope="row" className="max-w-64 px-4 py-3 font-normal">
                  <span className="block truncate font-medium text-foreground">
                    {account.display_name}
                    {isActor ? (
                      <span className="ml-2 text-xs font-normal text-muted-foreground">
                        (you)
                      </span>
                    ) : null}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {account.email}
                  </span>
                </th>
                <td className="px-4 py-3 align-top">
                  {isActor ? (
                    <div className="flex flex-col gap-1">
                      <Badge variant={PLATFORM_ROLE_BADGES[account.platform_role]}>
                        {PLATFORM_ROLE_LABELS[account.platform_role]}
                      </Badge>
                      {/* Mirrors the backend rule: an operator may not change their own role. */}
                      <span className="text-xs text-muted-foreground">
                        Your own role cannot be changed here.
                      </span>
                    </div>
                  ) : (
                    <PlatformRoleSelect account={account} />
                  )}
                </td>
                <td className="px-4 py-3 align-top">
                  {account.disabled_at ? (
                    <div className="flex flex-col gap-1">
                      <Badge variant="danger">Disabled</Badge>
                      <span className="text-xs text-muted-foreground">
                        since {formatAccountDate(account.disabled_at)}
                      </span>
                      {account.disabled_reason ? (
                        <span className="max-w-48 text-xs text-muted-foreground">
                          {account.disabled_reason}
                        </span>
                      ) : null}
                    </div>
                  ) : (
                    <Badge variant="success">Active</Badge>
                  )}
                </td>
                <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                  {formatAccountDate(account.created_at)}
                </td>
                <td className="px-4 py-3 text-right align-top">
                  {isActor ? null : <AccountStatusAction account={account} />}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
