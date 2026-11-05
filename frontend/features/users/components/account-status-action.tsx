"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { disableAccount, enableAccount } from "@/features/users/api/user-mutations";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { AccountAdmin } from "@/types/auth";

/**
 * Disable or re-enable an account, from the platform console.
 *
 * This is how an individual is stopped: a disabled account cannot sign in and
 * every session it holds ends immediately. Its data and memberships are kept,
 * so re-enabling is safe --- the person simply signs in again. The reason is kept
 * on the operator record and never shown to the account.
 *
 * Not rendered for the operator's own row: the backend refuses that, and the
 * console should not offer a button that cannot work.
 */
export function AccountStatusAction({ account }: { account: AccountAdmin }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const disabled = account.disabled_at !== null;

  function run(action: () => Promise<unknown>, fallback: string) {
    setError(null);
    setConfirming(false);
    startTransition(async () => {
      try {
        await action();
        setReason("");
        router.refresh();
      } catch (err) {
        setError(feedbackFromError(err, fallback).generalError ?? fallback);
      }
    });
  }

  if (disabled) {
    return (
      <div className="flex flex-col items-end gap-1">
        <Button
          variant="secondary"
          size="sm"
          disabled={isPending}
          aria-label={`Enable ${account.display_name}`}
          onClick={() => run(() => enableAccount(account.id), "Enable failed")}
        >
          {isPending ? "Enabling…" : "Enable"}
        </Button>
        {error ? (
          <p role="alert" className="max-w-44 text-right text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
    );
  }

  if (confirming) {
    return (
      <div className="flex flex-col items-end gap-2">
        <div>
          <label
            htmlFor={`disable-reason-${account.id}`}
            className="mb-1 block text-xs text-muted-foreground"
          >
            Reason (kept on the platform record)
          </label>
          <Input
            id={`disable-reason-${account.id}`}
            value={reason}
            maxLength={500}
            placeholder="abuse report, request, security…"
            onChange={(event) => setReason(event.target.value)}
            className="h-8 w-56 text-xs"
          />
        </div>
        <p className="max-w-56 text-right text-xs text-muted-foreground">
          They are signed out everywhere and cannot sign in until enabled.
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="danger"
            size="sm"
            disabled={isPending}
            onClick={() =>
              run(
                () => disableAccount(account.id, { reason: reason.trim() || null }),
                "Disable failed",
              )
            }
          >
            {isPending ? "Disabling…" : "Confirm disable"}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirming(false)} disabled={isPending}>
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setConfirming(true)}
        aria-label={`Disable ${account.display_name}`}
      >
        Disable
      </Button>
      {error ? (
        <p role="alert" className="max-w-44 text-right text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
