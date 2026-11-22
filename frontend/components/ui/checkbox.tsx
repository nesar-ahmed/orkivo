"use client";

import { type ComponentProps } from "react";
import { Check, Minus } from "lucide-react";
import { Checkbox as Primitive } from "radix-ui";
import { cn } from "@/lib/utils/cn";

/**
 * A checkbox on Radix: a real `role="checkbox"` with `aria-checked`, Space to
 * toggle, and a third "some of these" state (`checked="indeterminate"`) for a
 * select-all box. Always give it an accessible name (`aria-label`, or a label
 * pointing at its `id`).
 */
export function Checkbox({ className, checked, ...props }: ComponentProps<typeof Primitive.Root>) {
  return (
    <Primitive.Root
      checked={checked}
      className={cn(
        "inline-flex size-4 shrink-0 items-center justify-center rounded border border-border-strong bg-card shadow-xs",
        "transition-colors hover:border-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        "data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground",
        "data-[state=indeterminate]:border-primary data-[state=indeterminate]:bg-primary data-[state=indeterminate]:text-primary-foreground",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <Primitive.Indicator className="flex items-center justify-center">
        {checked === "indeterminate" ? (
          <Minus aria-hidden="true" className="size-3" strokeWidth={3} />
        ) : (
          <Check aria-hidden="true" className="size-3" strokeWidth={3} />
        )}
      </Primitive.Indicator>
    </Primitive.Root>
  );
}
