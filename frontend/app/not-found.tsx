import { SearchX } from "lucide-react";
import { ButtonLink } from "@/components/ui/button-link";
import { EmptyState } from "@/components/ui/empty-state";

/** Plain 404 outside the app: no session is read for a path that does not exist. */
export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-16">
      <div className="w-full max-w-md">
        <EmptyState
          icon={<SearchX />}
          title="Page not found"
          description="That address does not exist in Orkivo."
        >
          <ButtonLink href="/" variant="primary">
            Back to home
          </ButtonLink>
        </EmptyState>
      </div>
    </div>
  );
}
