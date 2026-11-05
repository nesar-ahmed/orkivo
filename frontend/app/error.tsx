"use client";

import { Button } from "@/components/ui/button";

/**
 * Error boundary for the whole app.
 *
 * Reached when a server read fails hard --- the API being stopped is the common
 * case. A session that is merely missing never comes here: the dashboard layout
 * redirects that to the sign-in screen, and only a genuine fault is allowed to
 * look like one.
 */
export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 py-16 text-center">
      <h1 className="text-lg font-semibold tracking-tight">Something went wrong</h1>
      <p className="max-w-md text-sm text-muted-foreground">{error.message}</p>
      <p className="max-w-md text-xs text-muted-foreground">
        If the Orkivo API is not running, start it with{" "}
        <code className="rounded bg-muted px-1 py-0.5 text-[0.7rem]">
          uv run uvicorn app.main:app --reload --port 8000
        </code>{" "}
        and try again.
      </p>
      {error.digest ? (
        <p className="text-xs text-muted-foreground">Reference: {error.digest}</p>
      ) : null}
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
