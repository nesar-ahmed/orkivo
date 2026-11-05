"use client";

import { type ComponentProps, type ReactNode } from "react";
import { X } from "lucide-react";
import { Dialog as Primitive } from "radix-ui";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

/**
 * Modal dialogs on Radix: focus is trapped and returned, Escape closes, the page
 * behind is inert and hidden from assistive technology.
 */
export const Dialog = Primitive.Root;
export const DialogTrigger = Primitive.Trigger;
export const DialogClose = Primitive.Close;

export function DialogContent({
  className,
  children,
  title,
  description,
  hideClose,
  ...props
}: ComponentProps<typeof Primitive.Content> & {
  title: string;
  description?: ReactNode;
  hideClose?: boolean;
}) {
  return (
    <Primitive.Portal>
      <Primitive.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px] animate-fade-in" />
      <Primitive.Content
        className={cn(
          "fixed top-[12vh] left-1/2 z-50 w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 rounded-xl border border-border",
          "bg-popover p-5 text-popover-foreground shadow-lg animate-pop-in focus:outline-none",
          className,
        )}
        // Without a description Radix warns; `undefined` tells it there is none on purpose.
        {...(description ? {} : { "aria-describedby": undefined })}
        {...props}
      >
        <div className="mb-4 flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <Primitive.Title className="text-base font-semibold">{title}</Primitive.Title>
            {description ? (
              <Primitive.Description className="mt-1 text-sm text-muted-foreground">
                {description}
              </Primitive.Description>
            ) : null}
          </div>
          {hideClose ? null : (
            <Primitive.Close asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Close">
                <X aria-hidden="true" />
              </Button>
            </Primitive.Close>
          )}
        </div>
        {children}
      </Primitive.Content>
    </Primitive.Portal>
  );
}

/**
 * Ask before something that cannot be undone. Reversible actions should offer
 * Undo instead of asking (see `toaster.tsx`).
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  destructive = true,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  destructive?: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={title} description={description} hideClose className="max-w-md">
        <div className="flex justify-end gap-2">
          <DialogClose asChild>
            <Button variant="secondary" size="sm">
              Cancel
            </Button>
          </DialogClose>
          <Button
            variant={destructive ? "danger-solid" : "primary"}
            size="sm"
            onClick={() => {
              onConfirm();
              onOpenChange(false);
            }}
          >
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
