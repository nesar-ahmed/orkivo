"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  AtSign,
  Bell,
  CheckCheck,
  CircleCheck,
  LockOpen,
  MessageSquare,
  UserRoundCheck,
} from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  markAllNotificationsRead,
  markNotificationRead,
} from "@/features/notifications/api/notification-mutations";
import { fetchNotifications } from "@/features/notifications/api/notification-queries";
import {
  badgeCount,
  notificationHeadline,
  notificationHref,
} from "@/features/notifications/notification-utils";
import { useUnreadCount } from "@/features/notifications/use-unread-count";
import { formatTimestamp } from "@/features/tasks/task-utils";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";
import type { AppNotification, NotificationKind } from "@/types/notification";

/** How many notifications the popover shows; the newest ones. */
const INBOX_SIZE = 20;

const KIND_ICONS: Record<NotificationKind, typeof Bell> = {
  assigned: UserRoundCheck,
  commented: MessageSquare,
  mentioned: AtSign,
  unblocked: LockOpen,
  completed: CircleCheck,
};

/**
 * The inbox: a bell with the unread count, opening the newest notifications.
 *
 * The list is read when the popover opens, so it is always current. Opening a
 * notification marks it read and goes to its task; "Mark all as read" clears the
 * badge. Everything shown was decided by the backend --- only the caller's own
 * notifications, only from workspaces they still belong to.
 */
export function NotificationBell({ initialUnread }: { initialUnread: number }) {
  const router = useRouter();
  const { count, refresh, setCount } = useUnreadCount(initialUnread);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const page = await fetchNotifications({ page_size: INBOX_SIZE });
      setItems(page.items);
      setCount(page.unread);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Notifications could not be loaded.");
    }
  }

  async function openNotification(notification: AppNotification) {
    setOpen(false);
    if (!notification.read_at) {
      setCount(Math.max(count - 1, 0));
      await markNotificationRead(notification.id).catch(() => refresh());
    }
    router.push(notificationHref(notification));
  }

  async function markAll() {
    setItems((current) =>
      current?.map((item) => ({ ...item, read_at: item.read_at ?? new Date().toISOString() })) ??
      null,
    );
    setCount(0);
    await markAllNotificationsRead().catch(() => refresh());
  }

  const label = count > 0 ? `Notifications, ${count} unread` : "Notifications";

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) void load();
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={label} className="relative">
          <Bell aria-hidden="true" />
          {count > 0 ? (
            <span
              aria-hidden="true"
              className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[0.625rem] font-semibold text-white ring-2 ring-background"
            >
              {badgeCount(count)}
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent aria-label="Notifications" className="w-[min(24rem,calc(100vw-1.5rem))] p-0">
        <header className="flex items-center gap-2 border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">Notifications</h2>
          <Button
            variant="ghost"
            size="xs"
            className="ml-auto"
            onClick={() => void markAll()}
            disabled={count === 0}
          >
            <CheckCheck aria-hidden="true" />
            Mark all as read
          </Button>
        </header>

        <div className="max-h-[min(28rem,70vh)] overflow-y-auto">
          {error ? (
            <p role="alert" className="px-4 py-6 text-sm text-danger">
              {error}
            </p>
          ) : items === null ? (
            <p className="px-4 py-6 text-sm text-muted-foreground">Loading…</p>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center gap-1 px-4 py-10 text-center">
              <Bell aria-hidden="true" className="size-5 text-muted-foreground" />
              <p className="text-sm font-medium">You are all caught up</p>
              <p className="text-xs text-muted-foreground">
                Assignments, comments on tasks you watch, and mentions appear here.
              </p>
            </div>
          ) : (
            <ul aria-label="Latest notifications" className="divide-y divide-border">
              {items.map((notification) => (
                <li key={notification.id}>
                  <NotificationRow
                    notification={notification}
                    onOpen={() => void openNotification(notification)}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function NotificationRow({
  notification,
  onOpen,
}: {
  notification: AppNotification;
  onOpen: () => void;
}) {
  const unread = notification.read_at === null;
  const Icon = KIND_ICONS[notification.kind];
  const who = notification.actor?.display_name ?? "A former member";
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "flex w-full gap-3 px-4 py-3 text-left transition-colors hover:bg-muted focus-visible:bg-muted focus-visible:outline-none",
        unread && "bg-primary/5",
      )}
    >
      <span className="relative shrink-0">
        <Avatar name={who} seed={notification.actor?.id} size="md" />
        <span className="absolute -right-1 -bottom-1 flex size-4 items-center justify-center rounded-full bg-card text-muted-foreground ring-1 ring-border [&_svg]:size-2.5">
          <Icon aria-hidden="true" />
        </span>
      </span>
      <span className="min-w-0 flex-1 text-sm">
        <span className="block text-foreground">
          {notificationHeadline(notification)}{" "}
          <span className="font-medium">“{notification.task.title}”</span>
        </span>
        {notification.excerpt ? (
          <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">
            {notification.excerpt}
          </span>
        ) : null}
        <span className="mt-1 block text-xs text-muted-foreground">
          {notification.workspace.kind === "personal" ? "Private" : notification.workspace.name}
          {" · "}
          <time dateTime={notification.created_at}>{formatTimestamp(notification.created_at)}</time>
        </span>
      </span>
      {unread ? (
        <span className="mt-1.5 size-2 shrink-0 rounded-full bg-primary">
          <span className="sr-only">Unread</span>
        </span>
      ) : null}
    </button>
  );
}
