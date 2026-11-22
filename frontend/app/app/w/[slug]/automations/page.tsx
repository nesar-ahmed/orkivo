import type { Metadata } from "next";
import { AutomationsScreen, fetchAutomations } from "@/features/automations";
import { loadCompany } from "../load-company";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { workspace } = await loadCompany(params);
  return { title: `${workspace.name} · Automations` };
}

/**
 * A company's automation rules. Every member sees which are on; owners, admins and
 * managers switch them. The read runs as the visitor, so the backend decides.
 */
export default async function CompanyAutomationsPage({ params }: PageProps) {
  const { workspace, cookie } = await loadCompany(params);
  const rules = await fetchAutomations(workspace.id, cookie);

  return <AutomationsScreen workspace={workspace} rules={rules} />;
}
