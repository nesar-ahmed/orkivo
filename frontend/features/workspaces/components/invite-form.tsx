"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { inviteMember } from "@/features/workspaces/api/workspace-mutations";
import {
  INVITABLE_ROLES,
  WORKSPACE_ROLE_LABELS,
} from "@/features/workspaces/workspace-utils";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { InvitableRole } from "@/types/workspace";

/**
 * Add a person to the company.
 *
 * Nothing is emailed: this opens an offer that the addressee finds when they sign
 * in with that address, which is why the flow works today and why adding a mail
 * transport later changes nothing here. Ownership is not on offer --- only an
 * owner hands that over, and the API refuses it even if this select were
 * tampered with.
 */
export function InviteForm({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    const form = event.currentTarget;
    event.preventDefault();
    const data = new FormData(form);

    startTransition(async () => {
      try {
        await inviteMember(workspaceId, {
          email: String(data.get("email") ?? ""),
          role: (String(data.get("role") ?? "member") as InvitableRole) || "member",
        });
        form.reset();
        setFieldErrors({});
        setMessage({ tone: "ok", text: "Invitation opened. They will see it when they sign in." });
        router.refresh();
      } catch (error) {
        const feedback = feedbackFromError(error, "The invitation could not be opened.");
        setFieldErrors(feedback.fieldErrors);
        setMessage(
          feedback.generalError ? { tone: "bad", text: feedback.generalError } : null,
        );
      }
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      aria-label="Invite someone to this workspace"
      className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-sm"
    >
      <div>
        <label htmlFor="invite-email" className="mb-1 block text-xs font-medium text-foreground">
          Email address <span aria-hidden="true">*</span>
        </label>
        <Input
          id="invite-email"
          name="email"
          type="email"
          required
          autoComplete="off"
          placeholder="colleague@example.com"
          aria-invalid={Boolean(fieldErrors.email)}
          disabled={isPending}
        />
        {fieldErrors.email ? (
          <p role="alert" className="mt-1 text-xs text-danger">
            {fieldErrors.email}
          </p>
        ) : null}
      </div>

      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label htmlFor="invite-role" className="mb-1 block text-xs font-medium text-foreground">
            Role offered
          </label>
          <Select id="invite-role" name="role" defaultValue="member" disabled={isPending}>
            {INVITABLE_ROLES.map((role) => (
              <option key={role} value={role}>
                {WORKSPACE_ROLE_LABELS[role]}
              </option>
            ))}
          </Select>
        </div>
        <Button type="submit" disabled={isPending}>
          {isPending ? "Opening…" : "Invite"}
        </Button>
      </div>

      <p aria-live="polite" className="text-xs">
        {message ? (
          <span className={message.tone === "ok" ? "text-success" : "text-danger"}>
            {message.text}
          </span>
        ) : (
          <span className="text-muted-foreground">
            They join as soon as they accept from their profile. No owner role is offered.
          </span>
        )}
      </p>
    </form>
  );
}
