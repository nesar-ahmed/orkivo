import { type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";
import { fieldStyles } from "./input";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  className?: string;
}

export function Textarea({ className, ...props }: TextareaProps) {
  return (
    <textarea
      className={cn(fieldStyles, "h-auto min-h-20 resize-y py-2 leading-relaxed", className)}
      {...props}
    />
  );
}
