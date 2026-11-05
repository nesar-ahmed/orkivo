import { type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

export const fieldStyles =
  "h-9 w-full rounded-md border border-border bg-card px-3 text-sm text-card-foreground " +
  "shadow-xs transition-[border-color,box-shadow] placeholder:text-muted-foreground " +
  "hover:border-border-strong focus-visible:border-primary focus-visible:outline-none " +
  "focus-visible:ring-3 focus-visible:ring-primary/20 " +
  "aria-invalid:border-danger aria-invalid:ring-danger/20 disabled:opacity-60";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  className?: string;
}

export function Input({ className, ...props }: InputProps) {
  return <input className={cn(fieldStyles, className)} {...props} />;
}
