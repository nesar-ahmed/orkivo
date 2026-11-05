import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

export type BadgeVariant = "neutral" | "primary" | "info" | "success" | "warning" | "danger";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

/** Subtle tint plus a hairline ring: readable on any surface, in both themes. */
const variantStyles: Record<BadgeVariant, string> = {
  neutral: "bg-muted text-muted-foreground ring-border",
  primary: "bg-primary/10 text-primary ring-primary/20",
  info: "bg-info/10 text-info ring-info/20",
  success: "bg-success/10 text-success ring-success/20",
  warning: "bg-warning/10 text-warning ring-warning/20",
  danger: "bg-danger/10 text-danger ring-danger/20",
};

export function Badge({ variant = "neutral", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        "ring-1 ring-inset [&_svg]:size-3",
        variantStyles[variant],
        className,
      )}
      {...props}
    />
  );
}
