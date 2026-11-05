import Link from "next/link";
import { redirect } from "next/navigation";
import { DEFAULT_POST_AUTH_PATH, RegisterForm, tryReadCurrentUser } from "@/features/auth";
import { getServerCookieHeader } from "@/lib/api/server-cookies";

export const dynamic = "force-dynamic";

export const metadata = { title: "Create an account" };

interface PageProps {
  searchParams: Promise<{ next?: string }>;
}

/**
 * Registration screen. New accounts are members and stay that way: no field
 * here can name a role, and the administrator role is granted by the backend
 * alone (architecture doc section 9).
 */
export default async function RegisterPage({ searchParams }: PageProps) {
  const cookie = await getServerCookieHeader();
  const visitor = await tryReadCurrentUser(cookie);
  if (visitor) redirect(DEFAULT_POST_AUTH_PATH);

  const { next } = await searchParams;

  return (
    <>
      <h2 className="mb-4 text-sm font-semibold text-card-foreground">Create an account</h2>
      <RegisterForm next={next} />

      <p className="mt-5 border-t border-border pt-4 text-center text-xs text-muted-foreground">
        Already registered?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </>
  );
}
