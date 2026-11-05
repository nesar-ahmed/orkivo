import { cn } from "@/lib/utils/cn";

/** Soft background + readable initial, picked deterministically from the id. */
const TONES = [
  "bg-[#e0e7ff] text-[#3730a3]",
  "bg-[#dcfce7] text-[#166534]",
  "bg-[#fee2e2] text-[#991b1b]",
  "bg-[#fef3c7] text-[#92400e]",
  "bg-[#e0f2fe] text-[#075985]",
  "bg-[#f3e8ff] text-[#6b21a8]",
  "bg-[#fce7f3] text-[#9d174d]",
  "bg-[#ccfbf1] text-[#115e59]",
];

function toneFor(seed: string): string {
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = (hash * 31 + seed.charCodeAt(index)) | 0;
  }
  return TONES[Math.abs(hash) % TONES.length] ?? TONES[0]!;
}

export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0]![0], parts[parts.length - 1]![0]] : [parts[0]?.[0]];
  return letters.filter(Boolean).join("").toUpperCase() || "?";
}

/**
 * A person's initials in a colored circle. Decorative by default: the name is
 * always written next to it or given as the `label`, never only drawn.
 */
export function Avatar({
  name,
  seed,
  size = "md",
  label,
  className,
}: {
  name: string;
  /** Stable id for the color, so renaming does not repaint someone. */
  seed?: string;
  size?: "xs" | "sm" | "md";
  /** Accessible name when the avatar stands alone. */
  label?: string;
  className?: string;
}) {
  const sizes = { xs: "size-5 text-[0.6rem]", sm: "size-6 text-[0.65rem]", md: "size-8 text-xs" };
  return (
    <span
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold select-none",
        sizes[size],
        toneFor(seed ?? name),
        className,
      )}
    >
      {initialsOf(name)}
    </span>
  );
}
