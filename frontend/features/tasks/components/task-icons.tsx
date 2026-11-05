import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import type { TaskPriority, TaskStatus } from "@/types/task";

/**
 * Status as a shape, not only a color: an empty ring for "To do", a half-filled
 * ring for "In progress" and a filled check for "Done". Decorative --- the label
 * is always rendered or announced next to it.
 */
export function StatusIcon({ status, className }: { status: TaskStatus; className?: string }) {
  const common = cn("size-4 shrink-0", className);
  if (status === "done") {
    return (
      <svg viewBox="0 0 16 16" aria-hidden="true" className={cn(common, "text-status-done")}>
        <circle cx="8" cy="8" r="7" fill="currentColor" />
        <path
          d="M5 8.2 7 10.2 11 6"
          fill="none"
          stroke="var(--card)"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (status === "in_progress") {
    return (
      <svg viewBox="0 0 16 16" aria-hidden="true" className={cn(common, "text-status-progress")}>
        <circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M8 3.5a4.5 4.5 0 0 1 0 9z" fill="currentColor" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className={cn(common, "text-status-todo")}>
      <circle
        cx="8"
        cy="8"
        r="6.25"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="2.6 1.6"
      />
    </svg>
  );
}

/** Priority as a direction: up for high, flat for medium, down for low. */
export function PriorityIcon({
  priority,
  className,
}: {
  priority: TaskPriority;
  className?: string;
}) {
  const common = cn("size-4 shrink-0", className);
  if (priority === "high") return <ArrowUp aria-hidden="true" className={cn(common, "text-priority-high")} />;
  if (priority === "low") return <ArrowDown aria-hidden="true" className={cn(common, "text-priority-low")} />;
  return <Minus aria-hidden="true" className={cn(common, "text-priority-medium")} />;
}
