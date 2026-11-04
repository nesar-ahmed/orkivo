import { type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

export const fieldStyles =
  "h-10 w-full rounded-md border border-border bg-card px-3 text-sm text-card-foreground " +
  "shadow-sm transition-colors placeholder:text-muted-foreground " +
  "focus-visible:border-primary aria-invalid:border-danger";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  className?: string;
}

export function Input({ className, ...props }: InputProps) {
  return <input className={cn(fieldStyles, className)} {...props} />;
}
