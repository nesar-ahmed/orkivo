"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { login } from "@/features/auth/api/auth-api";
import { safeRedirectTarget } from "@/features/auth/auth-policy";
import { feedbackFromError } from "@/lib/api/form-feedback";

/**
 * Sign-in form. On success the backend has set the session cookies, so the
 * server-rendered dashboard is re-fetched rather than patched from the client.
 *
 * ``next`` is where the guard was heading. It is validated before use so a
 * crafted query string cannot turn a successful login into an outbound redirect.
 */
export function LoginForm({ next }: { next?: string }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    const form = event.currentTarget;
    event.preventDefault();
    const data = new FormData(form);

    startTransition(async () => {
      try {
        await login({
          email: String(data.get("email") ?? ""),
          password: String(data.get("password") ?? ""),
        });
        setFieldErrors({});
        setGeneralError(null);
        router.replace(safeRedirectTarget(next));
        router.refresh();
      } catch (error) {
        const feedback = feedbackFromError(
          error,
          "Could not sign in. Please check your details and try again.",
        );
        setFieldErrors(feedback.fieldErrors);
        setGeneralError(feedback.generalError);
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Sign in to Orkivo" className="flex flex-col gap-4">
      <div>
        <label htmlFor="login-email" className="mb-1 block text-xs font-medium text-foreground">
          Email <span aria-hidden="true">*</span>
        </label>
        <Input
          id="login-email"
          name="email"
          type="email"
          required
          autoComplete="email"
          placeholder="you@example.com"
          aria-invalid={Boolean(fieldErrors.email)}
          aria-describedby={fieldErrors.email ? "login-email-error" : undefined}
          disabled={isPending}
        />
        {fieldErrors.email ? (
          <p id="login-email-error" role="alert" className="mt-1 text-xs text-danger">
            {fieldErrors.email}
          </p>
        ) : null}
      </div>

      <div>
        <label
          htmlFor="login-password"
          className="mb-1 block text-xs font-medium text-foreground"
        >
          Password <span aria-hidden="true">*</span>
        </label>
        <Input
          id="login-password"
          name="password"
          type="password"
          required
          autoComplete="current-password"
          aria-invalid={Boolean(fieldErrors.password)}
          aria-describedby={fieldErrors.password ? "login-password-error" : undefined}
          disabled={isPending}
        />
        {fieldErrors.password ? (
          <p id="login-password-error" role="alert" className="mt-1 text-xs text-danger">
            {fieldErrors.password}
          </p>
        ) : null}
      </div>

      {/* The backend returns one generic message: it never says which half was wrong. */}
      {generalError ? (
        <p
          role="alert"
          className="rounded-md border border-danger/40 bg-danger/10 p-3 text-xs text-danger"
        >
          {generalError}
        </p>
      ) : null}

      <Button type="submit" disabled={isPending}>
        {isPending ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
