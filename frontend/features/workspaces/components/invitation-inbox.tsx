"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  acceptInvitation,
  declineInvitation,
} from "@/features/workspaces/api/workspace-mutations";
import { WORKSPACE_ROLE_LABELS } from "@/features/workspaces/workspace-utils";
import { feedbackFromError } from "@/lib/api/form-feedback";
import { formatAccountDate } from "@/features/users/user-utils";
import type { WorkspaceInvitation } from "@/types/workspace";

/**
 * The invitations waiting on this account.
 *
 * This is the delivery mechanism, not a placeholder for one: an offer exists
 * because someone with authority in a company opened it for this exact address,
 * and nothing becomes access until the addressee accepts. Declining leaves the
 * door shut but re-openable.
 */
export function InvitationInbox({ invitations }: { invitations: WorkspaceInvitation[] }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (invitations.length === 0) return null;

  function act(invitation: WorkspaceInvitation, action: "accept" | "decline") {
    setBusyId(invitation.id);
    setError(null);

    startTransition(async () => {
      try {
        if (action === "accept") {
          const joined = await acceptInvitation(invitation.id);
          // Landing on the company you just joined reads better than a toast that
          // says you are now somewhere you cannot see.
          router.push(`/app/workspaces/${joined.id}/people`);
        } else {
          await declineInvitation(invitation.id);
        }
        router.refresh();
      } catch (err) {
        setError(
          feedbackFromError(
            err,
            action === "accept"
              ? "The invitation could not be accepted."
              : "The invitation could not be declined.",
          ).generalError ?? "The invitation could not be handled.",
        );
      } finally {
        setBusyId(null);
      }
    });
  }

  return (
    <section
      aria-labelledby="invitations-heading"
      className="rounded-xl border border-primary/40 bg-primary/5 p-5"
    >
      <h2 id="invitations-heading" className="text-sm font-semibold text-card-foreground">
        Invitations
      </h2>
      <p className="mt-1 text-xs text-muted-foreground">
        Companies that have opened a place for this address. Nothing changes until you accept.
      </p>

      <ul className="mt-4 flex flex-col gap-3">
        {invitations.map((invitation) => (
          <li
            key={invitation.id}
            className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-card-foreground">
                {invitation.workspace_name}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                As {WORKSPACE_ROLE_LABELS[invitation.role]}
                {invitation.invited_by_name ? ` · by ${invitation.invited_by_name}` : ""} ·{" "}
                {formatAccountDate(invitation.created_at)}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={() => act(invitation, "accept")}
                disabled={busyId !== null || isPending}
                aria-label={`Join ${invitation.workspace_name}`}
              >
                {busyId === invitation.id ? "Working…" : "Join"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => act(invitation, "decline")}
                disabled={busyId !== null || isPending}
                aria-label={`Decline the invitation from ${invitation.workspace_name}`}
              >
                Decline
              </Button>
            </div>
          </li>
        ))}
      </ul>

      {error ? (
        <p role="alert" className="mt-3 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </section>
  );
}
