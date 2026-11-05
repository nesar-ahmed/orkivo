import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { cookies } from "next/headers";
import { Toaster } from "@/components/ui/toaster";
import { THEME_COOKIE, explicitTheme } from "@/lib/theme/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Orkivo — Think. Organize. Build.",
    template: "%s — Orkivo",
  },
  description:
    "Orkivo is a work management platform. Organize tasks, projects and insights. AI-assisted features are planned.",
};

/**
 * The document shell.
 *
 * Fonts are self-hosted (`geist` ships the files with the app), so building needs
 * no network. The theme is rendered here from the person's cookie: an explicit
 * choice becomes `data-theme`, and "system" leaves it off so CSS follows the OS.
 * Reading the cookie makes every page render per request --- the price of a
 * theme that is right on the first paint, on every page, without a script.
 */
export default async function RootLayout({ children }: LayoutProps<"/">) {
  const theme = explicitTheme((await cookies()).get(THEME_COOKIE)?.value);

  return (
    <html
      lang="en"
      data-theme={theme}
      className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
