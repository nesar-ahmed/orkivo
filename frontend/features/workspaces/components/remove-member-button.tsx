"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { removeMember } from "@/features/workspaces/api/workspace-mutations";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { WorkspaceMember } from "@/types/workspace";

/**
 * Remove a member, or leave the company.
 *
 * A destructive control asks first --- with plain DOM state, not a dialog hook,
 * because the confirmation has to be part of the same accessible flow that
 * triggered it. The API still refuses the two things that must never succeed: an
 * admin removing the owner, and the last owner leaving.
 */
export function RemoveMemberButton({
  workspaceId,
  member,
  isActor,
}: {
  workspaceId: string;
  member: WorkspaceMember;
  isActor: boolean;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const label = isActor ? "Leave" : "Remove";

  function handleConfirm() {
    setError(null);
    setConfirming(false);

    startTransition(async () => {
      try {
        await removeMember(workspaceId, member.user_id);
        // Leaving a company is a change to *which* tenants the caller has, so the
        // people screen is no longer theirs to view.
        if (isActor) {
          router.replace("/app/workspaces");
        }
        router.refresh();
      } catch (err) {
        setError(
          feedbackFromError(err, `${label} was refused.`).generalError ?? `${label} was refused.`,
        );
      }
    });
  }

  if (confirming) {
    return (
      <div className="flex flex-col items-end gap-1">
        <div className="flex items-center gap-2">
          <Button
            variant="danger"
            size="sm"
            onClick={handleConfirm}
            disabled={isPending}
            aria-label={`${label} ${member.display_name}`}
          >
            {isPending ? "Working…" : `Confirm ${label.toLowerCase()}`}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setConfirming(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
        </div>
        <p className="max-w-48 text-right text-xs text-muted-foreground">
          {isActor
            ? "You will lose access to this company until someone invites you again."
            : `${member.display_name} will lose access until they are invited again.`}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setConfirming(true)}
        disabled={isPending}
        aria-label={`${label} ${member.display_name}`}
      >
        {label}
      </Button>
      {error ? (
        <p role="alert" className="max-w-48 text-right text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
