import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { TenantAction } from "@/features/workspaces/components/tenant-action";
import { formatAccountDate } from "@/features/users/user-utils";
import {
  WORKSPACE_KIND_LABELS,
  WORKSPACE_STATUS_BADGES,
  WORKSPACE_STATUS_LABELS,
} from "@/features/workspaces/workspace-utils";
import type { TenantAdmin } from "@/types/workspace";

/**
 * The platform console&rsquo;s tenant list.
 *
 * What an operator can see is decided by the response type, not by restraint in
 * the UI: this row has a head count and a lifecycle state, and there is no link
 * into anyone&rsquo;s tasks, because the API does not offer one (architecture doc
 * section 9).
 */
export function TenantTable({ tenants }: { tenants: TenantAdmin[] }) {
  if (tenants.length === 0) {
    return (
      <EmptyState
        title="No tenants match"
        description="Try a different search term, or clear the filters."
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
      <table className="w-full min-w-[40rem] text-left text-sm">
        <caption className="sr-only">
          Every tenant on the platform: kind, head count, lifecycle state and age.
        </caption>
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-3 font-medium">
              Tenant
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Kind
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              People
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Status
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Opened
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              <span className="sr-only">Lifecycle</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {tenants.map((tenant) => (
            <tr key={tenant.id}>
              <th scope="row" className="max-w-64 px-4 py-3 font-normal">
                <span className="block truncate font-medium text-foreground">{tenant.name}</span>
                <span className="block truncate font-mono text-xs text-muted-foreground">
                  {tenant.slug ?? "no address"}
                </span>
              </th>
              <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                {WORKSPACE_KIND_LABELS[tenant.kind]}
              </td>
              <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                {tenant.member_count}
              </td>
              <td className="px-4 py-3 align-top">
                <Badge variant={WORKSPACE_STATUS_BADGES[tenant.status]}>
                  {WORKSPACE_STATUS_LABELS[tenant.status]}
                </Badge>
                {tenant.operator_note ? (
                  <span className="ml-2 text-xs text-muted-foreground">{tenant.operator_note}</span>
                ) : null}
              </td>
              <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                {formatAccountDate(tenant.created_at)}
              </td>
              <td className="px-4 py-3 text-right align-top">
                <TenantAction tenant={tenant} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
