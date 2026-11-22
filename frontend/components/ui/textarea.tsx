import { type ComponentProps } from "react";
import { cn } from "@/lib/utils/cn";
import { fieldStyles } from "./input";

/** Every `<textarea>` prop, `ref` included (a plain prop in React 19). */
export interface TextareaProps extends ComponentProps<"textarea"> {
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
