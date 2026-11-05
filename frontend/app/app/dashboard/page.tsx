import { redirect } from "next/navigation";
import { PERSONAL_WORKSPACE_PATH } from "@/features/workspaces";

/**
 * `/app/dashboard` is what old bookmarks and links point at. Tasks now live in a
 * workspace, so it forwards to the private board, which is also where sign-in
 * lands (`DEFAULT_POST_AUTH_PATH`); the switcher moves on from there.
 */
export default function DashboardPage() {
  redirect(`${PERSONAL_WORKSPACE_PATH}/tasks`);
}
