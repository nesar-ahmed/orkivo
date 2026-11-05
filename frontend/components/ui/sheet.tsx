"use client";

import { type ComponentProps } from "react";
import { Dialog as Primitive } from "radix-ui";
import { cn } from "@/lib/utils/cn";

/**
 * A panel that slides in from the left edge: the navigation drawer on small
 * screens. It is a modal dialog underneath, so focus is trapped inside while it
 * is open and returns to the menu button when it closes.
 */
export const Sheet = Primitive.Root;
export const SheetTrigger = Primitive.Trigger;
export const SheetClose = Primitive.Close;

export function SheetContent({
  className,
  children,
  title,
  ...props
}: ComponentProps<typeof Primitive.Content> & { title: string }) {
  return (
    <Primitive.Portal>
      <Primitive.Overlay className="fixed inset-0 z-50 bg-black/40 animate-fade-in" />
      <Primitive.Content
        aria-describedby={undefined}
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r border-border bg-sidebar",
          "shadow-lg animate-slide-in-left focus:outline-none",
          className,
        )}
        {...props}
      >
        <Primitive.Title className="sr-only">{title}</Primitive.Title>
        {children}
      </Primitive.Content>
    </Primitive.Portal>
  );
}
