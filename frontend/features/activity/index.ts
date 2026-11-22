/** Public surface of the activity feature (read-only). */

export { ActivityFeed } from "./components/activity-feed";
export { ActivityItem } from "./components/activity-item";
export { fetchTaskActivity, fetchWorkspaceActivity } from "./api/activity-queries";
export { describeActivity, isAutomated, isShownAsComment } from "./activity-utils";
