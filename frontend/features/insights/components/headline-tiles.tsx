import { CalendarClock, CalendarRange, CircleDot, TriangleAlert } from "lucide-react";
import type { StatTile } from "@/features/insights/components/stat-tiles";
import { percent, tasksLabel } from "@/features/insights/insight-utils";
import { StatusIcon } from "@/features/tasks/components/task-icons";
import type { TaskCounts } from "@/types/insights";

/** Where each headline number leads. */
export interface HeadlineLinks {
  readonly open: string;
  readonly inProgress: string;
  readonly overdue: string;
  readonly today: string;
  readonly week: string;
  readonly done: string;
}

/** The six headline numbers both dashboards open with. */
export function headlineTiles(totals: TaskCounts, links: HeadlineLinks): StatTile[] {
  return [
    {
      key: "open",
      label: "Open",
      value: totals.open,
      href: links.open,
      icon: <CircleDot aria-hidden="true" />,
      hint: `of ${tasksLabel(totals.total)}`,
    },
    {
      key: "in_progress",
      label: "In progress",
      value: totals.in_progress,
      href: links.inProgress,
      icon: <StatusIcon status="in_progress" />,
      hint: `${percent(totals.in_progress, totals.open)}% of open`,
    },
    {
      key: "overdue",
      label: "Overdue",
      value: totals.overdue,
      href: links.overdue,
      icon: <TriangleAlert aria-hidden="true" />,
      hint: totals.overdue > 0 ? "Past their due date" : "Nothing late",
      tone: "attention",
    },
    {
      key: "today",
      label: "Due today",
      value: totals.due_today,
      href: links.today,
      icon: <CalendarClock aria-hidden="true" />,
    },
    {
      key: "week",
      label: "Next 7 days",
      value: totals.due_next_7_days,
      href: links.week,
      icon: <CalendarRange aria-hidden="true" />,
    },
    {
      key: "done",
      label: "Done",
      value: totals.done,
      href: links.done,
      icon: <StatusIcon status="done" />,
      hint: `${percent(totals.done, totals.total)}% of all tasks`,
    },
  ];
}
