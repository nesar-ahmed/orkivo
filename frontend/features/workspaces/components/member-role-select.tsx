"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Select } from "@/components/ui/select";
import { changeMemberRole } from "@/features/workspaces/api/workspace-mutations";
import {
  ASSIGNABLE_ROLES,
  WORKSPACE_ROLE_LABELS,
} from "@/features/workspaces/workspace-utils";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { WorkspaceMember, WorkspaceRole } from "@/types/workspace";

/**
 * Move someone between owner, admin and member.
 *
 * The value comes from the server, not local state: on success the re-read
 * supplies the new role, on failure the old one stays. Demoting the last owner is
 * refused by the API, and that refusal is what this control shows --- the rule is
 * not duplicated here.
 */
export function MemberRoleSelect({
  workspaceId,
  member,
}: {
  workspaceId: string;
  member: WorkspaceMember;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function handleChange(next: WorkspaceRole) {
    if (next === member.role) return;
    setError(null);

    startTransition(async () => {
      try {
        await changeMemberRole(workspaceId, member.user_id, { role: next });
        router.refresh();
      } catch (err) {
        setError(
          feedbackFromError(err, "The role change was refused.").generalError ??
            "The role change was refused.",
        );
      }
    });
  }

  return (
    <div className="flex flex-col gap-1">
      <Select
        aria-label={`Role for ${member.display_name}`}
        value={member.role}
        onChange={(event) => handleChange(event.target.value as WorkspaceRole)}
        disabled={isPending}
        className="h-8 max-w-36 text-xs"
      >
        {ASSIGNABLE_ROLES.map((role) => (
          <option key={role} value={role}>
            {WORKSPACE_ROLE_LABELS[role]}
          </option>
        ))}
      </Select>

      {isPending ? (
        <span aria-live="polite" className="text-xs text-muted-foreground">
          Saving…
        </span>
      ) : null}
      {error ? (
        <p role="alert" className="max-w-48 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
