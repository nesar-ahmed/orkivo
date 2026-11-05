"use client";

import { Toaster as Sonner } from "sonner";

/**
 * The app's one notification region. Notifications are announced politely to
 * screen readers, stack at the bottom right, and carry an Undo action where an
 * action is reversible --- Undo instead of "Are you sure?" for anything that can
 * be taken back.
 *
 * Call sites use `toast()` from `sonner` directly.
 */
export function Toaster() {
  return (
    <Sonner
      position="bottom-right"
      // Always laid out in full: a stack that expands on hover moves the Undo and
      // close buttons out from under the pointer that is reaching for them.
      expand
      visibleToasts={3}
      closeButton
      toastOptions={{
        classNames: {
          toast:
            "!rounded-lg !border !border-border !bg-popover !text-popover-foreground !shadow-md !font-sans",
          description: "!text-muted-foreground",
          actionButton: "!bg-primary !text-primary-foreground !font-medium",
          closeButton: "!border-border !bg-popover !text-muted-foreground",
        },
      }}
    />
  );
}
