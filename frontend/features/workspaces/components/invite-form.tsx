"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { inviteMember } from "@/features/workspaces/api/workspace-mutations";
import { InvitePersonPicker } from "@/features/workspaces/components/invite-person-picker";
import {
  WORKSPACE_ROLE_DESCRIPTIONS,
  WORKSPACE_ROLE_LABELS,
} from "@/features/workspaces/workspace-utils";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { InvitableRole, InviteCandidate } from "@/types/workspace";

/**
 * Add a person to the company.
 *
 * Only people with an Orkivo account can be invited: the person is chosen from
 * the picker --- never the inviter, and never an address nobody registered --- and
 * the API refuses anyone else. Nothing is emailed: the offer appears in the
 * person's profile the next time they look, which is why adding a mail transport
 * later changes nothing here.
 *
 * `roles` is what the inviter may offer: the workspace's `grantable_roles`
 * without ownership, which is never invited. An admin is therefore not offered
 * "Admin" --- only an owner makes one --- and the API refuses both even if this
 * select were tampered with.
 */
export function InviteForm({
  workspaceId,
  roles,
}: {
  workspaceId: string;
  /** In rank order; never empty when the caller may invite. */
  roles: readonly InvitableRole[];
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [person, setPerson] = useState<InviteCandidate | null>(null);
  const initialRole: InvitableRole = roles.includes("member") ? "member" : (roles[0] ?? "member");
  const [role, setRole] = useState<InvitableRole>(initialRole);
  const [generation, setGeneration] = useState(0);
  const [message, setMessage] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!person) {
      setMessage({ tone: "bad", text: "Choose who to invite first." });
      return;
    }

    startTransition(async () => {
      try {
        await inviteMember(workspaceId, { user_id: person.id, role });
        setMessage({
          tone: "ok",
          text: `Invitation sent to ${person.display_name}. They will see it in their profile.`,
        });
        setPerson(null);
        setRole(initialRole);
        // A fresh picker, so the next search does not show stale standings.
        setGeneration((value) => value + 1);
        router.refresh();
      } catch (error) {
        const feedback = feedbackFromError(error, "The invitation could not be sent.");
        setMessage({ tone: "bad", text: feedback.generalError ?? "Please check the form." });
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
        <label htmlFor="invite-person" className="mb-1 block text-xs font-medium text-foreground">
          Person <span aria-hidden="true">*</span>
        </label>
        <InvitePersonPicker
          key={generation}
          workspaceId={workspaceId}
          value={person}
          onChange={(next) => {
            setPerson(next);
            setMessage(null);
          }}
          disabled={isPending}
          describedBy="invite-message"
        />
      </div>

      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label htmlFor="invite-role" className="mb-1 block text-xs font-medium text-foreground">
            Role offered
          </label>
          <Select
            id="invite-role"
            name="role"
            value={role}
            onChange={(event) => setRole(event.target.value as InvitableRole)}
            disabled={isPending}
            aria-describedby="invite-role-description"
          >
            {roles.map((value) => (
              <option key={value} value={value}>
                {WORKSPACE_ROLE_LABELS[value]}
              </option>
            ))}
          </Select>
        </div>
        <Button type="submit" disabled={isPending || !person}>
          {isPending ? "Sending…" : "Invite"}
        </Button>
      </div>
      <p id="invite-role-description" className="-mt-1 text-xs text-muted-foreground">
        {WORKSPACE_ROLE_DESCRIPTIONS[role]}
      </p>

      <p id="invite-message" aria-live="polite" className="text-xs">
        {message ? (
          <span className={message.tone === "ok" ? "text-success" : "text-danger"}>
            {message.text}
          </span>
        ) : (
          <span className="text-muted-foreground">
            Only people with an Orkivo account can be invited. They join when they accept from
            their profile. Ownership is never offered by invitation.
          </span>
        )}
      </p>
    </form>
  );
}
