import { SearchX } from "lucide-react";
import { ButtonLink } from "@/components/ui/button-link";
import { EmptyState } from "@/components/ui/empty-state";

/**
 * Not found, inside the app: the sidebar and switcher stay put, so a dead link
 * costs one click instead of a trip through the marketing page.
 *
 * The wording is the same for "does not exist" and "not yours to see" on
 * purpose --- the API refuses to tell them apart, and so does this page.
 */
export default function AppNotFound() {
  return (
    <div className="mx-auto max-w-lg py-16">
      <EmptyState
        icon={<SearchX />}
        title="Page not found"
        description="This page does not exist, or you do not have access to it. If someone shared the link, ask them to check you are a member of that workspace."
      >
        <ButtonLink href="/app/personal/tasks" variant="primary">
          Go to your tasks
        </ButtonLink>
      </EmptyState>
    </div>
  );
}
