import { redirect } from "next/navigation";
import { WORKSPACE_HOME_SECTION } from "@/features/workspaces";

interface PageProps {
  params: Promise<{ slug: string }>;
}

/**
 * `/app/w/acme` is the company itself; it opens on its overview --- where the
 * work stands and who holds it --- with the board one tab away.
 */
export default async function CompanyIndexPage({ params }: PageProps) {
  const { slug } = await params;
  redirect(`/app/w/${encodeURIComponent(slug)}/${WORKSPACE_HOME_SECTION}`);
}
