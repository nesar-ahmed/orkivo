"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  activateTenant,
  suspendTenant,
} from "@/features/workspaces/api/workspace-mutations";
import { feedbackFromError } from "@/lib/api/form-feedback";
import type { TenantAdmin } from "@/types/workspace";

/**
 * Suspend or restore a tenant.
 *
 * A note is required to suspend: an unexplained switch-off is the kind of thing
 * nobody can answer a week later, and the note is the only history this surface
 * keeps. Suspension stops the company&rsquo;s people from being added to it; it
 * deletes nothing, so restoring is safe.
 */
export function TenantAction({ tenant }: { tenant: TenantAdmin }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const suspended = tenant.status === "suspended";

  function run(action: () => Promise<unknown>, fallback: string) {
    setError(null);
    setConfirming(false);

    startTransition(async () => {
      try {
        await action();
        router.refresh();
      } catch (err) {
        setError(feedbackFromError(err, fallback).generalError ?? fallback);
      }
    });
  }

  if (suspended) {
    return (
      <div className="flex flex-col items-end gap-1">
        <Button
          variant="secondary"
          size="sm"
          disabled={isPending}
          aria-label={`Restore ${tenant.name}`}
          onClick={() => run(() => activateTenant(tenant.id, { note: note || undefined }), "Restore failed")}
        >
          {isPending ? "Restoring…" : "Restore"}
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
          <label htmlFor={`note-${tenant.id}`} className="mb-1 block text-xs text-muted-foreground">
            Reason (kept on the platform record)
          </label>
          <Input
            id={`note-${tenant.id}`}
            value={note}
            maxLength={500}
            placeholder="billing, abuse report, request…"
            onChange={(event) => setNote(event.target.value)}
            className="h-8 w-56 text-xs"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="danger"
            size="sm"
            disabled={isPending}
            onClick={() =>
              run(() => suspendTenant(tenant.id, { note: note.trim() || null }), "Suspend failed")
            }
          >
            {isPending ? "Suspending…" : "Confirm suspend"}
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
      <Button variant="ghost" size="sm" onClick={() => setConfirming(true)} aria-label={`Suspend ${tenant.name}`}>
        Suspend
      </Button>
      {error ? (
        <p role="alert" className="max-w-44 text-right text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
