import { redirect } from "next/navigation";
import { PERSONAL_WORKSPACE_PATH } from "@/features/workspaces";

/** The private workspace has one section today: its board. */
export default function PersonalIndexPage() {
  redirect(`${PERSONAL_WORKSPACE_PATH}/tasks`);
}
