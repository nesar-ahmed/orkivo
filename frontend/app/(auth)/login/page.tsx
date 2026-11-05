import Link from "next/link";
import { redirect } from "next/navigation";
import {
  DEFAULT_POST_AUTH_PATH,
  LoginForm,
  SessionRecovery,
  tryReadCurrentUser,
} from "@/features/auth";
import { getServerCookieHeader } from "@/lib/api/server-cookies";

export const dynamic = "force-dynamic";

export const metadata = { title: "Sign in" };

interface PageProps {
  searchParams: Promise<{ next?: string }>;
}

/**
 * Sign-in screen. Thin by design (architecture doc 8.1): it decides who is
 * already in and hands the rest to the auth feature.
 *
 * An unreadable session reads as "signed out" here --- every failure, including
 * an API that is down, has to leave a form to sign in with. The POST to
 * `/auth/login` is what reports the real problem.
 */
export default async function LoginPage({ searchParams }: PageProps) {
  const cookie = await getServerCookieHeader();
  const visitor = await tryReadCurrentUser(cookie);
  if (visitor) redirect(DEFAULT_POST_AUTH_PATH);

  const { next } = await searchParams;

  return (
    <>
      <SessionRecovery next={next} />
      <h2 className="mb-4 text-sm font-semibold text-card-foreground">Sign in</h2>
      <LoginForm next={next} />

      <p className="mt-5 border-t border-border pt-4 text-center text-xs text-muted-foreground">
        No account yet?{" "}
        <Link href="/register" className="font-medium text-primary hover:underline">
          Create one
        </Link>
      </p>
    </>
  );
}
