/**
 * The viewer's own calendar day, on the server as well as in the browser.
 *
 * "Overdue" and "due today" are questions about the calendar on the viewer's
 * wall, not the server's. The browser knows its IANA time zone; it keeps it in a
 * cookie (`TimezoneSync`), so a server render can count from the same day the
 * viewer sees. Without the cookie --- the very first render --- it is UTC, which
 * is also what `useToday` starts from before hydration.
 *
 * The cookie holds a time zone name and nothing else. It is not a credential and
 * grants nothing: the worst a forged value can do is shift one viewer's own
 * dashboard by a day, and an unknown name falls back to UTC.
 */

export const TIMEZONE_COOKIE = "orkivo_tz";

/** How long the browser keeps it; it is refreshed whenever the zone changes. */
export const TIMEZONE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

/** `YYYY-MM-DD` for `now` in `timeZone`, or in UTC when the zone is unknown. */
export function isoDayIn(timeZone: string | undefined, now: Date = new Date()): string {
  if (timeZone) {
    try {
      // `en-CA` formats a date as YYYY-MM-DD.
      return new Intl.DateTimeFormat("en-CA", {
        timeZone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(now);
    } catch {
      // Not a zone this runtime knows: fall through to UTC.
    }
  }
  return now.toISOString().slice(0, 10);
}
