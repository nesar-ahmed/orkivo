"use client";

import { type ComponentProps } from "react";
import { Popover as Primitive } from "radix-ui";
import { cn } from "@/lib/utils/cn";

/**
 * A floating panel anchored to a trigger, on Radix: focus moves in and comes
 * back, Escape and an outside click close it. For content richer than a menu
 * (the notification inbox) --- menus stay `dropdown-menu.tsx`.
 */
export const Popover = Primitive.Root;
export const PopoverTrigger = Primitive.Trigger;
export const PopoverClose = Primitive.Close;

export function PopoverContent({
  className,
  sideOffset = 8,
  align = "end",
  ...props
}: ComponentProps<typeof Primitive.Content>) {
  return (
    <Primitive.Portal>
      <Primitive.Content
        sideOffset={sideOffset}
        align={align}
        collisionPadding={12}
        className={cn(
          "z-50 rounded-xl border border-border bg-popover text-popover-foreground shadow-lg",
          "animate-pop-in focus:outline-none",
          className,
        )}
        {...props}
      />
    </Primitive.Portal>
  );
}
