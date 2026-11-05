"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { updateProfile } from "@/features/users/api/user-mutations";
import { feedbackFromError } from "@/lib/api/form-feedback";

/** Mirrors the backend profile contract (users/schemas.py ``DisplayName``). */
const DISPLAY_NAME_MAX_LENGTH = 100;

/**
 * Edit the signed-in account's display name.
 *
 * The address is not editable: the backend exposes no route for it, so the form
 * offers exactly what can change. Server-rendered data is re-read after a save
 * rather than patched from here, so the shell and this card cannot disagree.
 */
export function ProfileForm({ displayName }: { displayName: string }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [value, setValue] = useState(displayName);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  const trimmed = value.trim();
  const dirty = trimmed !== displayName;
  const canSave = dirty && trimmed.length > 0 && !isPending;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSave) return;

    startTransition(async () => {
      try {
        await updateProfile({ display_name: trimmed });
        setFieldErrors({});
        setMessage({ tone: "ok", text: "Profile updated." });
        router.refresh();
      } catch (error) {
        const feedback = feedbackFromError(error, "Could not save your profile. Try again.");
        setFieldErrors(feedback.fieldErrors);
        // Field errors are announced next to their input; the general message
        // covers everything else. A failure is never reported as a success.
        setMessage(feedback.generalError ? { tone: "bad", text: feedback.generalError } : null);
      }
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      aria-label="Update your profile"
      className="flex flex-col gap-4"
    >
      <div>
        <label
          htmlFor="profile-display-name"
          className="mb-1 block text-xs font-medium text-foreground"
        >
          Display name <span aria-hidden="true">*</span>
        </label>
        <Input
          id="profile-display-name"
          name="display_name"
          value={value}
          required
          maxLength={DISPLAY_NAME_MAX_LENGTH}
          onChange={(event) => setValue(event.target.value)}
          aria-invalid={Boolean(fieldErrors.display_name)}
          aria-describedby="profile-display-name-help profile-feedback"
          disabled={isPending}
        />
        <p id="profile-display-name-help" className="mt-1 text-xs text-muted-foreground">
          Up to {DISPLAY_NAME_MAX_LENGTH} characters. Shown in the navigation and the admin
          directory.
        </p>
        {fieldErrors.display_name ? (
          <p role="alert" className="mt-1 text-xs text-danger">
            {fieldErrors.display_name}
          </p>
        ) : null}
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={!canSave}>
          {isPending ? "Saving…" : "Save changes"}
        </Button>
        {dirty && !isPending ? (
          <button
            type="button"
            onClick={() => {
              setValue(displayName);
              setFieldErrors({});
              setMessage(null);
            }}
            className="text-xs font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            Discard
          </button>
        ) : null}
      </div>

      {/* One live region for both outcomes, so a screen reader hears the change. */}
      <p
        id="profile-feedback"
        aria-live="polite"
        className={
          message
            ? message.tone === "ok"
              ? "rounded-md border border-success/40 bg-success/10 p-2 text-xs text-success"
              : "rounded-md border border-danger/40 bg-danger/10 p-2 text-xs text-danger"
            : "sr-only"
        }
      >
        {message?.text ?? ""}
      </p>
    </form>
  );
}
