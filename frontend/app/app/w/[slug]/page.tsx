import { redirect } from "next/navigation";

interface PageProps {
  params: Promise<{ slug: string }>;
}

/** `/app/w/acme` is the company itself; its board is the page people mean. */
export default async function CompanyIndexPage({ params }: PageProps) {
  const { slug } = await params;
  redirect(`/app/w/${encodeURIComponent(slug)}/tasks`);
}
