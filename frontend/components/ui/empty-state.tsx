import { type ReactNode } from "react";

export interface EmptyStateProps {
  title: string;
  description?: string;
  /** A decorative icon, drawn in a soft tile above the title. */
  icon?: ReactNode;
  children?: ReactNode;
}

/** Shared empty/placeholder state (architecture doc 8.3). */
export function EmptyState({ title, description, icon, children }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-border-strong bg-card/60 px-6 py-12 text-center">
      {icon ? (
        <span
          aria-hidden="true"
          className="mb-3 flex size-10 items-center justify-center rounded-lg bg-muted text-muted-foreground [&_svg]:size-5"
        >
          {icon}
        </span>
      ) : null}
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? (
        <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      ) : null}
      {children ? <div className="mt-4 flex justify-center">{children}</div> : null}
    </div>
  );
}
