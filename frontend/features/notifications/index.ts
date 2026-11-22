/** Public surface of the notifications feature. */

export { NotificationBell } from "./components/notification-bell";
export { WatchButton } from "./components/watch-button";
export { fetchNotifications, fetchUnreadCount, fetchWatchers } from "./api/notification-queries";
export {
  markAllNotificationsRead,
  markNotificationRead,
  unwatchTask,
  watchTask,
} from "./api/notification-mutations";
export { notificationHeadline, notificationHref } from "./notification-utils";
