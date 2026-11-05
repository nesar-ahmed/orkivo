import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { TaskForm, TaskList } from "@/features/tasks";
import { fetchTasks } from "@/features/tasks/api/task-queries";
import { ApiError } from "@/lib/api/client";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import { cn } from "@/lib/utils/cn";
import type { TaskListResponse } from "@/types/task";

export const dynamic = "force-dynamic";

export const metadata = { title: "Tasks" };

/**
 * Thin page: it composes feature components and handles the
 * loading/empty/error states (architecture doc 8.2/8.3).
 *
 * The read runs as the visitor: without the forwarded cookie this server-side
 * call would be anonymous and the backend would refuse it, which is exactly the
 * difference between routing and authorization.
 */
export default async function TasksDashboardPage() {
  const cookie = await getServerCookieHeader();
  let data: TaskListResponse | null = null;
  let loadError: string | null = null;

  try {
    data = await fetchTasks({ page_size: 100 }, cookie);
  } catch (err) {
    loadError =
      err instanceof ApiError ? err.message : "Failed to load tasks. Please try again.";
  }

  const doneCount = data?.items.filter((task) => task.status === "done").length ?? 0;

  return (
    <div className="grid gap-8 md:grid-cols-[minmax(0,1fr)_20rem]">
      <section aria-labelledby="tasks-heading" className="min-w-0">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <h1 id="tasks-heading" className="text-xl font-semibold tracking-tight">
            Tasks
          </h1>
          {data ? (
            <div className="flex gap-2 text-xs">
              <Badge variant="neutral">{data.total} total</Badge>
              <Badge variant="success">{doneCount} done</Badge>
            </div>
          ) : null}
        </div>

        {loadError ? (
          <div
            role="alert"
            className="rounded-xl border border-danger/40 bg-danger/10 p-5 text-sm text-danger"
          >
            <p className="font-medium">Tasks could not be loaded.</p>
            <p className="mt-1 text-xs">{loadError}</p>
            <Link
              href="/app/dashboard"
              className={cn(
                "mt-3 inline-flex h-8 items-center justify-center rounded-md border border-border",
                "bg-card px-3 text-sm font-medium text-card-foreground hover:bg-muted",
              )}
            >
              Retry
            </Link>
          </div>
        ) : data ? (
          <TaskList tasks={data.items} />
        ) : null}
      </section>

      <aside className="md:sticky md:top-20 md:self-start">
        <TaskForm />
      </aside>
    </div>
  );
}
