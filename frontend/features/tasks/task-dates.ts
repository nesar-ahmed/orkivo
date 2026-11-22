/**
 * Calendar arithmetic on due dates.
 *
 * A due date is a calendar day with no time and no timezone, written `YYYY-MM-DD`
 * exactly as the API sends it. Every function here works on those strings, doing
 * the arithmetic on UTC midnights so that a daylight-saving change can never turn
 * "the next day" into the same day twice. The one place the viewer's own clock
 * matters --- what "today" is --- lives in `use-today.ts`.
 */

/** `YYYY-MM`: the month a calendar shows. */
export type MonthKey = string;

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
const MONTH = /^(\d{4})-(\d{2})$/;

/** Sunday first, as `en-US` (the locale every date in the product is written in). */
export const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

function utc(iso: string): Date {
  const [, year, month, day] = ISO_DATE.exec(iso) ?? [];
  return new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
}

function iso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/** Whether `value` is a real calendar day (`2026-02-30` is not). */
export function isIsoDate(value: string): boolean {
  return ISO_DATE.test(value) && iso(utc(value)) === value;
}

/** The day `days` after (or before, when negative) `date`. */
export function addDays(date: string, days: number): string {
  const next = utc(date);
  next.setUTCDate(next.getUTCDate() + days);
  return iso(next);
}

/** A `Date`'s own calendar day on the viewer's clock. */
export function localIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** The month a day falls in. */
export function monthOf(date: string): MonthKey {
  return date.slice(0, 7);
}

/** A `?month=` value, or `undefined` for anything that is not a plausible month. */
export function parseMonth(raw: string | undefined): MonthKey | undefined {
  const match = raw ? MONTH.exec(raw.trim()) : null;
  if (!match) return undefined;
  const year = Number(match[1]);
  const month = Number(match[2]);
  // The range a due date may fall in (see `MIN_DUE_DATE` / `MAX_DUE_DATE`).
  if (year < 1970 || year > 2100 || month < 1 || month > 12) return undefined;
  return `${match[1]}-${match[2]}`;
}

/** The month `delta` months after `month`. */
export function shiftMonth(month: MonthKey, delta: number): MonthKey {
  const [year, index] = month.split("-").map(Number);
  const date = new Date(Date.UTC(year!, index! - 1 + delta, 1));
  return iso(date).slice(0, 7);
}

/** "November 2026". */
export function monthTitle(month: MonthKey): string {
  return utc(`${month}-01`).toLocaleDateString("en-US", {
    timeZone: "UTC",
    month: "long",
    year: "numeric",
  });
}

/** "Thursday, November 12" --- how a day is named to a screen reader. */
export function dayTitle(date: string): string {
  return utc(date).toLocaleDateString("en-US", {
    timeZone: "UTC",
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

/** "Nov 12" --- a short day, for notifications. */
export function shortDay(date: string): string {
  return utc(date).toLocaleDateString("en-US", { timeZone: "UTC", month: "short", day: "numeric" });
}

/**
 * The days a month's grid shows: whole weeks, Sunday to Saturday, from the week
 * holding the 1st to the week holding the last day --- five or six rows.
 */
export function monthGrid(month: MonthKey): { first: string; last: string; days: string[] } {
  const start = utc(`${month}-01`);
  const first = addDays(iso(start), -start.getUTCDay());
  const end = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 0));
  const last = addDays(iso(end), 6 - end.getUTCDay());
  const days: string[] = [];
  for (let day = first; day <= last; day = addDays(day, 1)) days.push(day);
  return { first, last, days };
}

/** Where a due date sits relative to today, for a person's own list. */
export type DueBucket = "overdue" | "today" | "week" | "later" | "none";

export const DUE_BUCKET_ORDER: readonly DueBucket[] = ["overdue", "today", "week", "later", "none"];

export const DUE_BUCKET_LABELS: Record<DueBucket, string> = {
  overdue: "Overdue",
  today: "Today",
  week: "Next 7 days",
  later: "Later",
  none: "No due date",
};

/**
 * "Overdue", "today", "the next seven days", "later" or "none". Overdue is only
 * for work that is not done: a finished task due last week is simply "earlier",
 * which reads as later rather than as a warning.
 */
export function dueBucket(due: string | null, today: string, done: boolean): DueBucket {
  if (!due) return "none";
  if (due < today) return done ? "later" : "overdue";
  if (due === today) return "today";
  if (due <= addDays(today, 7)) return "week";
  return "later";
}

/**
 * The due-date filter a board's URL can carry (`?due=overdue`): the buckets
 * above, minus "later". It is what a dashboard's numbers link to, so "3 overdue"
 * opens exactly those three tasks.
 */
export type DueFilter = "overdue" | "today" | "week" | "none";

export const DUE_FILTERS: readonly DueFilter[] = ["overdue", "today", "week", "none"];

export const DUE_FILTER_LABELS: Record<DueFilter, string> = {
  overdue: "Overdue",
  today: "Due today",
  week: "Next 7 days",
  none: "No due date",
};

/** What a due filter asks the API for, on the viewer's `today`. */
export interface DueWindow {
  readonly due_from?: string;
  readonly due_to?: string;
  readonly has_due_date?: boolean;
  /**
   * Overdue is about work that is not done (`dueBucket`): without a status filter
   * of its own, the list is narrowed to open work, and a board's Done column is
   * empty.
   */
  readonly openOnly: boolean;
}

export function dueWindow(filter: DueFilter, today: string): DueWindow {
  switch (filter) {
    case "overdue":
      return { due_to: addDays(today, -1), openOnly: true };
    case "today":
      return { due_from: today, due_to: today, openOnly: false };
    case "week":
      return { due_from: addDays(today, 1), due_to: addDays(today, 7), openOnly: false };
    case "none":
      return { has_due_date: false, openOnly: false };
  }
}
