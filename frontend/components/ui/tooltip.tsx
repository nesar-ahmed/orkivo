"use client";

import { type ReactNode } from "react";
import { Tooltip as Primitive } from "radix-ui";

/**
 * A short hint on hover or keyboard focus. Never the only place information
 * lives: an icon button still carries its own `aria-label`.
 */
export function Tooltip({
  content,
  children,
  side = "top",
}: {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
}) {
  return (
    <Primitive.Root>
      <Primitive.Trigger asChild>{children}</Primitive.Trigger>
      <Primitive.Portal>
        <Primitive.Content
          side={side}
          sideOffset={6}
          className="z-50 max-w-64 rounded-md bg-foreground px-2 py-1 text-xs text-background shadow-md animate-fade-in"
        >
          {content}
        </Primitive.Content>
      </Primitive.Portal>
    </Primitive.Root>
  );
}

/** One provider for the app, so tooltips share their open/close delays. */
export function TooltipProvider({ children }: { children: ReactNode }) {
  return <Primitive.Provider delayDuration={300}>{children}</Primitive.Provider>;
}
