import { Tooltip } from "@/components/ui/tooltip";
import { LABEL_COLOR_STYLES } from "@/features/labels/label-utils";
import { cn } from "@/lib/utils/cn";
import type { LabelColor } from "@/types/label";

/** The fields every label-shaped value has, wherever it came from. */
interface LabelLike {
  readonly id: string;
  readonly name: string;
  readonly color: LabelColor;
}

/** A label's color as a small solid swatch. Decorative: the name is always next to it. */
export function LabelDot({ color, className }: { color: LabelColor; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block size-2 shrink-0 rounded-full", LABEL_COLOR_STYLES[color].dot, className)}
    />
  );
}

/** One label as a tinted pill. The color is never the only cue: the name is the text. */
export function LabelChip({ label, className }: { label: LabelLike; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex max-w-36 min-w-0 items-center gap-1 rounded-full px-1.5 py-px text-[0.7rem] font-medium",
        "ring-1 ring-inset",
        LABEL_COLOR_STYLES[label.color].chip,
        className,
      )}
    >
      <LabelDot color={label.color} className="size-1.5" />
      <span className="truncate">{label.name}</span>
    </span>
  );
}

/**
 * A task's labels as chips. Past `max`, the rest collapse into "+N", whose names
 * are on hover and for screen readers, so a busy task never pushes its row apart.
 */
export function LabelChips({
  labels,
  max = 3,
  className,
}: {
  labels: readonly LabelLike[];
  max?: number;
  className?: string;
}) {
  if (labels.length === 0) return null;
  const shown = labels.slice(0, max);
  const rest = labels.slice(max);
  return (
    <span className={cn("inline-flex min-w-0 flex-wrap items-center gap-1", className)}>
      <span className="sr-only">Labels: </span>
      {shown.map((label) => (
        <LabelChip key={label.id} label={label} />
      ))}
      {rest.length > 0 ? (
        <Tooltip content={rest.map((label) => label.name).join(", ")}>
          <span
            tabIndex={0}
            className="inline-flex items-center rounded-full bg-muted px-1.5 py-px text-[0.7rem] font-medium text-muted-foreground ring-1 ring-border ring-inset"
          >
            +{rest.length}
            <span className="sr-only"> more: {rest.map((label) => label.name).join(", ")}</span>
          </span>
        </Tooltip>
      ) : null}
    </span>
  );
}
