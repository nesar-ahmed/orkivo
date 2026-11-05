import { notFound } from "next/navigation";

/**
 * Any `/app/...` address no route matches. Without this, Next would answer with
 * the bare root 404 and the visitor would lose the app shell.
 */
export default function MissingAppPage() {
  notFound();
}
