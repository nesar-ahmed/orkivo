import { EmptyState } from "@/components/ui/empty-state";
import { TaskCard } from "@/features/tasks/components/task-card";
import type { Task } from "@/types/task";

/** Renders the task collection, including the empty state. */
export function TaskList({ tasks }: { tasks: Task[] }) {
  if (tasks.length === 0) {
    return (
      <EmptyState
        title="No tasks yet"
        description="Create your first task with the form on the right. Orkivo: Think. Organize. Build."
      />
    );
  }

  return (
    <ul className="flex flex-col gap-3" aria-label="Tasks">
      {tasks.map((task) => (
        <TaskCard key={task.id} task={task} />
      ))}
    </ul>
  );
}
