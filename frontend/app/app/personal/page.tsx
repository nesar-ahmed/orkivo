import { redirect } from "next/navigation";
import { PERSONAL_WORKSPACE_PATH, WORKSPACE_HOME_SECTION } from "@/features/workspaces";

/**
 * `/app/personal` is the private workspace itself; it opens on its overview ---
 * the person's own dashboard --- with the board one tab away.
 */
export default function PersonalIndexPage() {
  redirect(`${PERSONAL_WORKSPACE_PATH}/${WORKSPACE_HOME_SECTION}`);
}
