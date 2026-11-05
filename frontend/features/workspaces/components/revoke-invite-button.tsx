"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { revokeInvitation } from "@/features/workspaces/api/workspace-mutations";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { WorkspaceInvite } from "@/types/workspace";

/** Close an open offer. Already-joined accounts are unaffected. */
export function RevokeInviteButton({
  workspaceId,
  invite,
}: {
  workspaceId: string;
  invite: WorkspaceInvite;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function handleRevoke() {
    setError(null);

    startTransition(async () => {
      try {
        await revokeInvitation(workspaceId, invite.id);
        router.refresh();
      } catch (err) {
        setError(
          feedbackFromError(err, "The invitation could not be revoked.").generalError ??
            "The invitation could not be revoked.",
        );
      }
    });
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant="ghost"
        size="sm"
        onClick={handleRevoke}
        disabled={isPending}
        aria-label={`Revoke the invitation for ${invite.email}`}
      >
        {isPending ? "Revoking…" : "Revoke"}
      </Button>
      {error ? (
        <p role="alert" className="max-w-44 text-right text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
