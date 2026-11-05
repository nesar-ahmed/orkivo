import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

/** A placeholder block while content loads. Decorative: the page announces "Loading". */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}
