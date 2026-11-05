"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { login, register } from "@/features/auth/api/auth-api";
import { PASSWORD_MIN_LENGTH, safeRedirectTarget } from "@/features/auth/auth-policy";
import { feedbackFromError } from "@/lib/api/form-feedback";

/**
 * Registration form. Creating an account does not start a session, so the form
 * signs the new user straight in afterwards --- one less step, and the backend
 * still decides what a valid session is.
 *
 * The first account to sign in may be promoted to administrator by the
 * backend's ``FIRST_ADMIN_EMAIL`` setting; the role comes back on the session
 * response and the dashboard renders it. Nothing here asks for a role.
 */
export function RegisterForm({ next }: { next?: string }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    const form = event.currentTarget;
    event.preventDefault();
    const data = new FormData(form);
    const email = String(data.get("email") ?? "");
    const password = String(data.get("password") ?? "");
    const displayName = String(data.get("display_name") ?? "");

    startTransition(async () => {
      try {
        await register({
          email,
          password,
          display_name: displayName.length > 0 ? displayName : undefined,
        });
        await login({ email, password });
        setFieldErrors({});
        setGeneralError(null);
        router.replace(safeRedirectTarget(next));
        router.refresh();
      } catch (error) {
        const feedback = feedbackFromError(
          error,
          "Could not create the account. Please try again.",
        );
        setFieldErrors(feedback.fieldErrors);
        setGeneralError(feedback.generalError);
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Create an Orkivo account" className="flex flex-col gap-4">
      <div>
        <label
          htmlFor="register-email"
          className="mb-1 block text-xs font-medium text-foreground"
        >
          Email <span aria-hidden="true">*</span>
        </label>
        <Input
          id="register-email"
          name="email"
          type="email"
          required
          autoComplete="email"
          placeholder="you@example.com"
          aria-invalid={Boolean(fieldErrors.email)}
          aria-describedby={fieldErrors.email ? "register-email-error" : undefined}
          disabled={isPending}
        />
        {fieldErrors.email ? (
          <p id="register-email-error" role="alert" className="mt-1 text-xs text-danger">
            {fieldErrors.email}
          </p>
        ) : null}
      </div>

      <div>
        <label
          htmlFor="register-display-name"
          className="mb-1 block text-xs font-medium text-foreground"
        >
          Display name
        </label>
        <Input
          id="register-display-name"
          name="display_name"
          maxLength={100}
          placeholder="Optional — taken from your email if left blank"
          aria-invalid={Boolean(fieldErrors.display_name)}
          aria-describedby={fieldErrors.display_name ? "register-display-name-error" : undefined}
          disabled={isPending}
        />
        {fieldErrors.display_name ? (
          <p id="register-display-name-error" role="alert" className="mt-1 text-xs text-danger">
            {fieldErrors.display_name}
          </p>
        ) : null}
      </div>

      <div>
        <label
          htmlFor="register-password"
          className="mb-1 block text-xs font-medium text-foreground"
        >
          Password <span aria-hidden="true">*</span>
        </label>
        <Input
          id="register-password"
          name="password"
          type="password"
          required
          minLength={PASSWORD_MIN_LENGTH}
          autoComplete="new-password"
          aria-invalid={Boolean(fieldErrors.password)}
          aria-describedby="register-password-hint register-password-error"
          disabled={isPending}
        />
        <p id="register-password-hint" className="mt-1 text-xs text-muted-foreground">
          At least {PASSWORD_MIN_LENGTH} characters. Stored only as an Argon2id hash.
        </p>
        {fieldErrors.password ? (
          <p id="register-password-error" role="alert" className="mt-1 text-xs text-danger">
            {fieldErrors.password}
          </p>
        ) : null}
      </div>

      {generalError ? (
        <p
          role="alert"
          className="rounded-md border border-danger/40 bg-danger/10 p-3 text-xs text-danger"
        >
          {generalError}
        </p>
      ) : null}

      <Button type="submit" disabled={isPending}>
        {isPending ? "Creating account…" : "Create account"}
      </Button>
    </form>
  );
}
