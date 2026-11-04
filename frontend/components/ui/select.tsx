import { type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";
import { fieldStyles } from "./input";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  className?: string;
}

export function Select({ className, ...props }: SelectProps) {
  return <select className={cn(fieldStyles, "cursor-pointer", className)} {...props} />;
}
