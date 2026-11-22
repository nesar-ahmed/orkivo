import { redirect } from "next/navigation";
import { PERSONAL_WORKSPACE_PATH, WORKSPACE_HOME_SECTION } from "@/features/workspaces";

/**
 * `/app/dashboard` is what old bookmarks and links point at. The person's own
 * dashboard is the private workspace's overview, which is also where sign-in
 * lands (`DEFAULT_POST_AUTH_PATH`); the switcher moves on from there.
 */
export default function DashboardPage() {
  redirect(`${PERSONAL_WORKSPACE_PATH}/${WORKSPACE_HOME_SECTION}`);
}
