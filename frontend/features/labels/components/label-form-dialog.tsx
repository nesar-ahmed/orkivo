"use client";

import { useState, useTransition, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Check } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  createLabel,
  isLabelConflict,
  isLabelNameInUse,
  updateLabel,
} from "@/features/labels/api/label-mutations";
import { LabelChip } from "@/features/labels/components/label-chip";
import {
  LABEL_COLORS,
  LABEL_COLOR_NAMES,
  LABEL_COLOR_STYLES,
  LABEL_NAME_MAX_LENGTH,
} from "@/features/labels/label-utils";
import { ApiError } from "@/lib/api/client";
import { feedbackFromError } from "@/lib/api/form-feedback";
import { cn } from "@/lib/utils/cn";
import type { Label, LabelColor, LabelUpdateInput } from "@/types/label";

/**
 * Create a label, or rename and recolor an existing one, in a dialog.
 *
 * Editing sends only what changed, with the version the page loaded: if a
 * colleague saved in between, the API refuses and the dialog says so instead of
 * overwriting them. A name another label already uses --- in any letter case ---
 * is shown on the name field, since that is the one thing to fix. A preview shows
 * the chip exactly as tasks will.
 */
export function LabelFormDialog({
  workspaceId,
  label,
  trigger,
  shared,
}: {
  workspaceId: string;
  /** The label to edit; omit to create a new one. */
  label?: Label;
  trigger: ReactNode;
  shared: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [generation, setGeneration] = useState(0);
  const editing = label !== undefined;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        // A fresh form every time it opens.
        if (next) setGeneration((value) => value + 1);
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent
        title={editing ? "Edit label" : "New label"}
        description={
          shared
            ? "Everyone in this company can see it and tag tasks with it."
            : "Private: only you can see it."
        }
        className="max-w-md"
      >
        <LabelForm
          key={generation}
          workspaceId={workspaceId}
          label={label}
          onDone={() => setOpen(false)}
        />
      </DialogContent>
    </Dialog>
  );
}

function LabelForm({
  workspaceId,
  label,
  onDone,
}: {
  workspaceId: string;
  label?: Label;
  onDone: () => void;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [name, setName] = useState(label?.name ?? "");
  const [color, setColor] = useState<LabelColor>(label?.color ?? "blue");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Rendered in a dialog portal: keep the submit from reaching any form behind it.
    event.stopPropagation();
    const trimmed = name.trim();

    startTransition(async () => {
      try {
        if (label) {
          const changes: LabelUpdateInput = {};
          if (trimmed !== label.name) changes.name = trimmed;
          if (color !== label.color) changes.color = color;
          if (Object.keys(changes).length > 0) {
            await updateLabel(label.id, { ...changes, version: label.version });
            toast("Label saved", { description: trimmed });
          }
        } else {
          await createLabel(workspaceId, { name: trimmed, color });
          toast("Label created", { description: trimmed });
        }
        onDone();
        router.refresh();
      } catch (error) {
        if (isLabelNameInUse(error) && error instanceof ApiError) {
          setFieldErrors({ name: error.message });
          setGeneralError(null);
          return;
        }
        if (isLabelConflict(error)) {
          setFieldErrors({});
          setGeneralError(
            "Someone else changed this label a moment ago. Close this dialog to see their version.",
          );
          router.refresh();
          return;
        }
        const feedback = feedbackFromError(error, "The label could not be saved.");
        setFieldErrors(feedback.fieldErrors);
        setGeneralError(feedback.generalError);
      }
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      aria-label={label ? `Edit ${label.name}` : "Create a new label"}
      className="flex flex-col gap-4"
    >
      <div>
        <label htmlFor="label-name" className="mb-1.5 block text-xs font-medium text-muted-foreground">
          Name <span aria-hidden="true">*</span>
        </label>
        <Input
          id="label-name"
          name="name"
          required
          autoFocus
          maxLength={LABEL_NAME_MAX_LENGTH}
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="e.g. Bug, Design, Customer"
          aria-invalid={Boolean(fieldErrors.name)}
          aria-describedby={fieldErrors.name ? "label-name-error" : undefined}
          disabled={isPending}
        />
        {fieldErrors.name ? (
          <p id="label-name-error" role="alert" className="mt-1 text-xs text-danger">
            {fieldErrors.name}
          </p>
        ) : null}
      </div>

      <fieldset disabled={isPending}>
        <legend className="mb-1.5 text-xs font-medium text-muted-foreground">Color</legend>
        <div className="flex flex-wrap gap-1.5">
          {LABEL_COLORS.map((option) => (
            <label
              key={option}
              title={LABEL_COLOR_NAMES[option]}
              className={cn(
                "relative inline-flex size-7 cursor-pointer items-center justify-center rounded-full ring-offset-2 ring-offset-popover",
                "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                option === color && "ring-2 ring-border-strong",
                LABEL_COLOR_STYLES[option].dot,
              )}
            >
              <input
                type="radio"
                name="color"
                value={option}
                checked={option === color}
                onChange={() => setColor(option)}
                className="sr-only"
              />
              <span className="sr-only">{LABEL_COLOR_NAMES[option]}</span>
              {option === color ? (
                <Check aria-hidden="true" className="size-4 text-card" strokeWidth={3} />
              ) : null}
            </label>
          ))}
        </div>
        {fieldErrors.color ? (
          <p role="alert" className="mt-1 text-xs text-danger">
            {fieldErrors.color}
          </p>
        ) : null}
      </fieldset>

      <div className="flex items-center gap-2 rounded-md border border-dashed border-border bg-muted/40 px-3 py-2">
        <span className="text-xs text-muted-foreground">Preview</span>
        <LabelChip label={{ id: "preview", name: name.trim() || "Label", color }} />
      </div>

      {generalError ? (
        <p role="alert" className="rounded-md border border-danger/30 bg-danger/10 p-2.5 text-sm text-danger">
          {generalError}
        </p>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onDone} disabled={isPending}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={isPending || name.trim().length === 0}>
          {isPending ? "Saving…" : label ? "Save label" : "Create label"}
        </Button>
      </div>
    </form>
  );
}
