import type { ReactNode } from "react";
import { WorkspaceHeader } from "@/features/workspaces";
import { loadCompany } from "./load-company";

export const dynamic = "force-dynamic";

/**
 * A company, addressed by name: `/app/w/acme-robotics/...`.
 *
 * The header is rendered once for every page inside the company, so its name,
 * the caller's role and a suspension notice are always in view. Membership is
 * re-checked by the API on this request; the URL is only a name.
 */
export default async function CompanyLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ slug: string }>;
}) {
  const { workspace } = await loadCompany(params);

  return (
    <div className="flex flex-col gap-6">
      <WorkspaceHeader workspace={workspace} />
      {children}
    </div>
  );
}
