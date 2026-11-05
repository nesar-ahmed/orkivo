import { redirect } from "next/navigation";
import { DEFAULT_POST_AUTH_PATH } from "@/features/auth";

/**
 * `/app` is the product root, and the dashboard is its home.
 *
 * The path is kept working rather than left as a 404 because it is the URL
 * people guess at when they see `/app/profile` and `/app/admin/users` next to
 * it. The `/app` layout has already confirmed the session by then.
 */
export default function AppIndexPage() {
  redirect(DEFAULT_POST_AUTH_PATH);
}
