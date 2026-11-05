import Link from "next/link";
import { Badge } from "@/components/ui/badge";

export const metadata = {
  title: "Think. Organize. Build.",
  description:
    "Orkivo is a work management platform for tasks, projects and insights. Create an account or sign in — free to start, no card required.",
};

/** What the product does today, stated in terms a visitor can go and try. */
const FEATURES = [
  {
    title: "Tasks that stay yours",
    body: "Create a task with a title, notes, priority and a due date; move it between To do, In progress and Done with a labelled keyboard control. Overdue work is flagged, and the API behind the list searches, filters and paginates.",
  },
  {
    title: "Your own space, or a company",
    body: "Every account gets a private workspace the moment it registers. Open a company when you need one, add people by email address, and they join as member or admin from their own profile once they accept. Ownership is transferred by an owner, never handed out by an invitation.",
  },
  {
    title: "Credentials that stay put",
    body: "Passwords are stored only as Argon2id hashes. Sessions ride in HttpOnly SameSite=Lax cookies with a header check on every state change, a wrong email and a wrong password answer with one identical message, and the database is SQLite or PostgreSQL — yours.",
  },
] as const;

/**
 * Public landing page. Deliberately a server component with no client
 * JavaScript: the only interactive things on it are two links.
 *
 * Claims are limited to what is shipped (architecture doc section 1.2 and 15).
 * Projects, boards and task scoping are named as next, not as features.
 */
export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center gap-3 px-4">
          <span
            aria-hidden="true"
            className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground"
          >
            O
          </span>
          <span className="text-sm font-semibold tracking-tight">Orkivo</span>
          <nav aria-label="Account" className="ml-auto flex items-center gap-2">
            <Link
              href="/login"
              className="rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              Sign in
            </Link>
            <Link
              href="/register"
              className="inline-flex h-8 items-center justify-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover"
            >
              Create account
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4">
        <section aria-labelledby="hero-heading" className="py-16 text-center sm:py-24">
          <Badge variant="primary" className="mb-5">
            Early baseline — sign up and try it
          </Badge>
          <h1 id="hero-heading" className="text-3xl font-semibold tracking-tight sm:text-5xl">
            Think. Organize. Build.
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base text-muted-foreground sm:text-lg">
            Orkivo is a work management platform for tasks, projects and insights — structured
            enough for real work, small enough to understand in an afternoon.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/register"
              className="inline-flex h-11 items-center justify-center rounded-md bg-primary px-6 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover"
            >
              Create your account
            </Link>
            <Link
              href="/login"
              className="inline-flex h-11 items-center justify-center rounded-md border border-border bg-card px-6 text-sm font-medium text-card-foreground transition-colors hover:bg-muted"
            >
              I already have one
            </Link>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Registration creates a member account. No card, no trial clock.
          </p>
        </section>

        <section aria-labelledby="features-heading" className="pb-16">
          <h2 id="features-heading" className="sr-only">
            What Orkivo does today
          </h2>
          <ul className="grid gap-4 sm:grid-cols-3">
            {FEATURES.map((feature) => (
              <li
                key={feature.title}
                className="rounded-xl border border-border bg-card p-5 text-left shadow-sm"
              >
                <h3 className="text-sm font-semibold text-card-foreground">{feature.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{feature.body}</p>
              </li>
            ))}
          </ul>
        </section>

        <section
          aria-labelledby="roadmap-heading"
          className="mb-16 rounded-xl border border-dashed border-border bg-card/50 p-6 text-center"
        >
          <h2 id="roadmap-heading" className="text-sm font-semibold text-foreground">
            What comes next
          </h2>
          <p className="mx-auto mt-2 max-w-2xl text-sm text-muted-foreground">
            Work is scoped to the workspace that holds it, then projects inside a company, boards
            you can drag (with a keyboard route to the same place), comments and an activity trail.
            AI-assisted drafting stays behind a provider-independent interface, so no vendor becomes
            a requirement.
          </p>
        </section>
      </main>

      <footer className="border-t border-border py-6">
        <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-center gap-x-4 gap-y-2 px-4 text-xs text-muted-foreground">
          <span>Orkivo — Think. Organize. Build.</span>
          <Link href="/login" className="underline-offset-2 hover:text-foreground hover:underline">
            Sign in
          </Link>
          <Link
            href="/register"
            className="underline-offset-2 hover:text-foreground hover:underline"
          >
            Create account
          </Link>
          <span>Sample data is synthetic; demo addresses use example.com.</span>
        </div>
      </footer>
    </div>
  );
}
