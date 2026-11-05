/** Labels and badge variants for the *platform* account surface. */

import type { BadgeVariant } from "@/components/ui/badge";
import type { PlatformRole } from "@/types/auth";

export const PLATFORM_ROLE_LABELS: Record<PlatformRole, string> = {
  user: "Account",
  operator: "Operator",
};

/** An operator is an emphasis badge; an ordinary account is unmarked. */
export const PLATFORM_ROLE_BADGES: Record<PlatformRole, BadgeVariant> = {
  user: "neutral",
  operator: "primary",
};

/** Canonical option order for platform-role pickers; mirrors the backend enum. */
export const PLATFORM_ROLE_ORDER: PlatformRole[] = ["user", "operator"];

/**
 * Format a stored UTC timestamp for display.
 *
 * Pinned to `en-US` and UTC so the server-rendered text and any later client
 * render agree; only the date part is shown, which is all these columns carry
 * meaningfully.
 */
export function formatAccountDate(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) return isoTimestamp;
  return date.toLocaleDateString("en-US", {
    timeZone: "UTC",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
