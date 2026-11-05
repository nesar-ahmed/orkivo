/**
 * Light, dark, or follow the system: the person's choice, rendered by the server.
 *
 * The choice lives in a cookie, so the root layout can render `data-theme` on
 * <html> itself. React then owns the attribute: no script sets it, nothing can
 * flash the wrong theme, and no client re-render can drop it. (An inline script
 * that set it did lose it when React re-rendered the root, on in-app 404 pages.)
 *
 * "System" is simply no attribute: `globals.css` follows `prefers-color-scheme`
 * then, live, with no JavaScript at all.
 */

export type ThemePreference = "system" | "light" | "dark";

export const THEME_COOKIE = "orkivo_theme";

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

/** The explicit theme a cookie value asks for, or `undefined` to follow the system. */
export function explicitTheme(value: string | undefined): "light" | "dark" | undefined {
  return value === "light" || value === "dark" ? value : undefined;
}

export function readThemePreference(): ThemePreference {
  const match = document.cookie.match(new RegExp(`(?:^|; )${THEME_COOKIE}=([^;]*)`));
  return explicitTheme(match?.[1]) ?? "system";
}

/**
 * Save a preference and apply it to this page at once. The server renders the
 * same attribute from the cookie on every later request.
 */
export function applyThemePreference(preference: ThemePreference): void {
  if (preference === "system") {
    document.cookie = `${THEME_COOKIE}=; path=/; max-age=0; samesite=lax`;
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.cookie = `${THEME_COOKIE}=${preference}; path=/; max-age=${ONE_YEAR_SECONDS}; samesite=lax`;
    document.documentElement.setAttribute("data-theme", preference);
  }
}
