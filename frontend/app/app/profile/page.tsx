import { Badge } from "@/components/ui/badge";
import { readCurrentUserOnce } from "@/features/auth";
import { InvitationInbox, fetchMyInvitations } from "@/features/workspaces";
import { ProfileForm } from "@/features/users";
import {
  PLATFORM_ROLE_BADGES,
  PLATFORM_ROLE_LABELS,
  formatAccountDate,
} from "@/features/users/user-utils";
import { getServerCookieHeader } from "@/lib/api/server-cookies";

export const dynamic = "force-dynamic";

export const metadata = { title: "Profile" };

/**
 * The signed-in account: what it is, the one field it may change, and any company
 * that is waiting on it.
 *
 * Invitations live here because this is the one screen that is about the person
 * rather than about a tenant: an offer is addressed to an account, not to a
 * workspace, so it is shown where the account is (architecture doc section 5).
 */
export default async function ProfilePage() {
  const cookie = await getServerCookieHeader();
  const [user, invitations] = await Promise.all([
    readCurrentUserOnce(cookie),
    fetchMyInvitations(cookie),
  ]);

  return (
    <div className="grid gap-8 md:grid-cols-[minmax(0,1fr)_20rem]">
      <section aria-labelledby="profile-heading" className="min-w-0 flex flex-col gap-6">
        <h1 id="profile-heading" className="text-xl font-semibold tracking-tight">
          Profile
        </h1>

        <InvitationInbox invitations={invitations.items} />

        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-card-foreground">Display name</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            How your account appears in the navigation, in a company&rsquo;s people list, and on
            invitations you open.
          </p>
          <div className="mt-4">
            <ProfileForm displayName={user.display_name} />
          </div>
        </div>
      </section>

      <aside className="md:sticky md:top-20 md:self-start">
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-card-foreground">Account</h2>
          <dl className="mt-4 flex flex-col gap-3 text-xs">
            <div>
              <dt className="text-muted-foreground">Email</dt>
              <dd className="mt-0.5 break-words font-medium text-foreground">{user.email}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Platform role</dt>
              <dd className="mt-0.5">
                <Badge variant={PLATFORM_ROLE_BADGES[user.platform_role]}>
                  {PLATFORM_ROLE_LABELS[user.platform_role]}
                </Badge>
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Member since</dt>
              <dd className="mt-0.5 font-medium text-foreground">
                {formatAccountDate(user.created_at)}
              </dd>
            </div>
          </dl>

          <p className="mt-4 border-t border-border pt-3 text-xs text-muted-foreground">
            The address is fixed once registered, and a platform role is granted by an operator:
            neither can be changed from this page. Your role inside each company is listed under
            Workspaces.
          </p>
        </div>
      </aside>
    </div>
  );
}
