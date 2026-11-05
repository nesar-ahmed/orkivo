import Link from "next/link";
import { EmptyState } from "@/components/ui/empty-state";

/** Plain 404: no session is read for a path that does not exist. */
export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-16">
      <div className="w-full max-w-md">
        <EmptyState
          title="Page not found"
          description="That address does not exist in Orkivo."
        >
          <Link
            href="/"
            className="inline-flex h-8 items-center justify-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
          >
            Back to home
          </Link>
        </EmptyState>
      </div>
    </div>
  );
}
