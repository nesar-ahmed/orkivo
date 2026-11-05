"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createWorkspace } from "@/features/workspaces/api/workspace-mutations";
import { workspacePath } from "@/features/workspaces/workspace-utils";
import { feedbackFromError } from "@/lib/api/form-feedback";

/**
 * Open a company.
 *
 * The slug is typed once and drives the tenant's address from then on, so the
 * form shows what will actually be stored and normalizes the obvious typos
 * (uppercase, spaces) rather than bouncing the submit.
 */
export function CreateWorkspaceForm() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [touchedSlug, setTouchedSlug] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  const effectiveSlug = touchedSlug ? slug : slugFromName(name);
  const canSubmit = name.trim().length > 0 && effectiveSlug.length >= 3 && !isPending;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;

    startTransition(async () => {
      try {
        const team = await createWorkspace({ name: name.trim(), slug: effectiveSlug });
        // Straight to the people page: a new company's first job is inviting them.
        router.push(workspacePath(team, "people"));
        router.refresh();
      } catch (error) {
        const feedback = feedbackFromError(error, "The company could not be opened.");
        setFieldErrors(feedback.fieldErrors);
        setGeneralError(feedback.generalError);
      }
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      aria-label="Open a company workspace"
      className="rounded-xl border border-border bg-card p-5 shadow-sm"
    >
      <h2 className="text-sm font-semibold text-card-foreground">Open a company</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        You become its owner. People join when you add their address and they accept.
      </p>

      <div className="mt-4 flex flex-col gap-4">
        <div>
          <label htmlFor="workspace-name" className="mb-1 block text-xs font-medium text-foreground">
            Company name <span aria-hidden="true">*</span>
          </label>
          <Input
            id="workspace-name"
            name="name"
            value={name}
            required
            maxLength={120}
            placeholder="Acme Robotics"
            onChange={(event) => setName(event.target.value)}
            aria-invalid={Boolean(fieldErrors.name)}
            aria-describedby={fieldErrors.name ? "workspace-name-error" : undefined}
            disabled={isPending}
          />
          {fieldErrors.name ? (
            <p id="workspace-name-error" role="alert" className="mt-1 text-xs text-danger">
              {fieldErrors.name}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="workspace-slug" className="mb-1 block text-xs font-medium text-foreground">
            Address <span aria-hidden="true">*</span>
          </label>
          <Input
            id="workspace-slug"
            name="slug"
            value={effectiveSlug}
            required
            minLength={3}
            maxLength={63}
            inputMode="url"
            spellCheck={false}
            placeholder="acme-robotics"
            onChange={(event) => {
              setTouchedSlug(true);
              setSlug(slugify(event.target.value));
            }}
            aria-invalid={Boolean(fieldErrors.slug)}
            aria-describedby="workspace-slug-help"
            disabled={isPending}
          />
          <p id="workspace-slug-help" className="mt-1 text-xs text-muted-foreground">
            Lowercase letters, numbers and dashes. It becomes the tenant&rsquo;s address and is
            hardest to change later, so avoid &ldquo;general&rdquo;.
          </p>
          {fieldErrors.slug ? (
            <p role="alert" className="mt-1 text-xs text-danger">
              {fieldErrors.slug}
            </p>
          ) : null}
        </div>
      </div>

      {generalError ? (
        <p
          role="alert"
          className="mt-3 rounded-md border border-danger/40 bg-danger/10 p-2 text-xs text-danger"
        >
          {generalError}
        </p>
      ) : null}

      <Button type="submit" className="mt-5 w-full" disabled={!canSubmit}>
        {isPending ? "Opening…" : "Open company"}
      </Button>
    </form>
  );
}

/** Lowercase, dashes instead of spaces, nothing the backend would reject. */
function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 63);
}

function slugFromName(name: string): string {
  return slugify(name);
}
