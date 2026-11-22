"use client";

import { type ComponentProps } from "react";
import { Switch as Primitive } from "radix-ui";
import { cn } from "@/lib/utils/cn";

/**
 * An on/off switch on Radix: a real `role="switch"` with `aria-checked`, toggled by
 * Space or Enter. For settings that take effect at once; a form field that is
 * saved later is a checkbox. Always give it an accessible name.
 */
export function Switch({ className, ...props }: ComponentProps<typeof Primitive.Root>) {
  return (
    <Primitive.Root
      className={cn(
        "inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-transparent bg-border-strong transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        "data-[state=checked]:bg-primary disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <Primitive.Thumb className="block size-4 translate-x-0.5 rounded-full bg-card shadow-xs transition-transform data-[state=checked]:translate-x-[1.125rem]" />
    </Primitive.Root>
  );
}
