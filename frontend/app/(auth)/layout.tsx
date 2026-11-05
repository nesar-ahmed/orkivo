import type { ReactNode } from "react";

/**
 * Public authentication shell: one centered card, no application navigation.
 *
 * Kept separate from the dashboard shell on purpose (architecture doc 8.1) ---
 * a signed-out visitor must never be handed the chrome of a signed-in one.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <span
            aria-hidden="true"
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-lg font-bold text-primary-foreground"
          >
            O
          </span>
          <h1 className="text-base font-semibold tracking-tight text-foreground">Orkivo</h1>
          <p className="text-xs text-muted-foreground">Think. Organize. Build.</p>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-sm">{children}</div>
      </div>

      <p className="text-center text-xs text-muted-foreground">
        Your session is kept in HttpOnly cookies: no token is stored in this browser&rsquo;s
        scripts.
      </p>
    </div>
  );
}
