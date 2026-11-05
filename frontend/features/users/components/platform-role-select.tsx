"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Select } from "@/components/ui/select";
import { PLATFORM_ROLE_LABELS, PLATFORM_ROLE_ORDER } from "@/features/users/user-utils";
import { updatePlatformRole } from "@/features/users/api/user-mutations";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { PlatformRole, User } from "@/types/auth";

/**
 * Change one account's *platform* role.
 *
 * The selected value comes from the server, not from local state: on success the
 * re-read supplies the new role, on failure the old one stays. This control is
 * about who may run the platform --- it has no bearing on any company, which is
 * what the workspace role picker is for (architecture doc section 5).
 */
export function PlatformRoleSelect({ account }: { account: User }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function handleChange(next: PlatformRole) {
    if (next === account.platform_role) return;
    setError(null);

    startTransition(async () => {
      try {
        await updatePlatformRole(account.id, { platform_role: next });
        router.refresh();
      } catch (err) {
        setError(
          feedbackFromError(err, "The platform role change was refused.").generalError ??
            "The platform role change was refused.",
        );
      }
    });
  }

  return (
    <div className="flex flex-col gap-1">
      <Select
        aria-label={`Platform role for ${account.display_name}`}
        value={account.platform_role}
        onChange={(event) => handleChange(event.target.value as PlatformRole)}
        disabled={isPending}
        className="h-8 max-w-36 text-xs"
      >
        {PLATFORM_ROLE_ORDER.map((role) => (
          <option key={role} value={role}>
            {PLATFORM_ROLE_LABELS[role]}
          </option>
        ))}
      </Select>

      {isPending ? (
        <span aria-live="polite" className="text-xs text-muted-foreground">
          Saving…
        </span>
      ) : null}
      {error ? (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
