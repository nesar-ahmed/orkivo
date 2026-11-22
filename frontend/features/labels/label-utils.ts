/** Presentation metadata and small helpers for the labels feature. */

import { workspacePath } from "@/features/workspaces/workspace-utils";
import type { LabelColor } from "@/types/label";
import type { Workspace } from "@/types/workspace";

/** Mirrors the backend's name limit, so the field never accepts what the API refuses. */
export const LABEL_NAME_MAX_LENGTH = 50;

/** Mirrors `MAX_LABELS_PER_TASK`: a picker stops offering more once a task is full. */
export const MAX_LABELS_PER_TASK = 20;

/** The palette, in the order a color picker offers it (backend `LabelColor`). */
export const LABEL_COLORS: readonly LabelColor[] = [
  "gray",
  "red",
  "orange",
  "yellow",
  "green",
  "teal",
  "blue",
  "indigo",
  "purple",
  "pink",
];

export const LABEL_COLOR_NAMES: Record<LabelColor, string> = {
  gray: "Gray",
  red: "Red",
  orange: "Orange",
  yellow: "Yellow",
  green: "Green",
  teal: "Teal",
  blue: "Blue",
  indigo: "Indigo",
  purple: "Purple",
  pink: "Pink",
};

/**
 * Classes for each color, spelled out in full so Tailwind can see them. `chip` is
 * a tint with a hairline ring, like `Badge`; `dot` is the solid swatch. Both read
 * the `--label-*` tokens in `globals.css`, so a theme changes them in one place.
 */
export const LABEL_COLOR_STYLES: Record<LabelColor, { chip: string; dot: string }> = {
  gray: { chip: "bg-label-gray/10 text-label-gray ring-label-gray/25", dot: "bg-label-gray" },
  red: { chip: "bg-label-red/10 text-label-red ring-label-red/25", dot: "bg-label-red" },
  orange: {
    chip: "bg-label-orange/10 text-label-orange ring-label-orange/25",
    dot: "bg-label-orange",
  },
  yellow: {
    chip: "bg-label-yellow/10 text-label-yellow ring-label-yellow/25",
    dot: "bg-label-yellow",
  },
  green: { chip: "bg-label-green/10 text-label-green ring-label-green/25", dot: "bg-label-green" },
  teal: { chip: "bg-label-teal/10 text-label-teal ring-label-teal/25", dot: "bg-label-teal" },
  blue: { chip: "bg-label-blue/10 text-label-blue ring-label-blue/25", dot: "bg-label-blue" },
  indigo: {
    chip: "bg-label-indigo/10 text-label-indigo ring-label-indigo/25",
    dot: "bg-label-indigo",
  },
  purple: {
    chip: "bg-label-purple/10 text-label-purple ring-label-purple/25",
    dot: "bg-label-purple",
  },
  pink: { chip: "bg-label-pink/10 text-label-pink ring-label-pink/25", dot: "bg-label-pink" },
};

/** The workspace's tasks, filtered to one label: where a label's task count leads. */
export function labelTasksHref(
  workspace: Pick<Workspace, "kind" | "slug">,
  labelId: string,
): string {
  return `${workspacePath(workspace, "tasks")}?label=${encodeURIComponent(labelId)}`;
}

/**
 * Labels in the order the API lists them: alphabetical, ignoring case. Used after
 * an optimistic edit, before the server's own order arrives.
 */
export function sortLabels<T extends { name: string; id: string }>(labels: readonly T[]): T[] {
  return [...labels].sort(
    (a, b) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: "base" }) || a.id.localeCompare(b.id),
  );
}
