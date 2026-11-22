import type { ReactNode } from "react";

/**
 * The layout of a task's own page: the task itself, then what it depends on, and
 * its discussion, both under the main column --- aligned with the title and
 * description, not the side panel.
 *
 * Separate regions on purpose. The task is an edit form; dependencies and the
 * discussion have their own controls and forms; none may be nested in another.
 */
export function TaskPage({
  detail,
  dependencies,
  discussion,
}: {
  detail: ReactNode;
  dependencies?: ReactNode;
  discussion: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-8">
      {detail}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="flex min-w-0 flex-col gap-8">
          {dependencies ? <div className="border-t border-border pt-6">{dependencies}</div> : null}
          <div className="border-t border-border pt-6">{discussion}</div>
        </div>
      </div>
    </div>
  );
}
