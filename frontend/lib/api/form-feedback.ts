/**
 * Translate the backend error contract into form state.
 *
 * Field-level validation details map onto their inputs; anything else becomes a
 * single general message. Shared by the task, auth and profile forms so the
 * error affordance behaves the same everywhere (architecture doc section 8.3).
 */

import { ApiError } from "@/lib/api/client";

export interface FormFeedback {
  readonly fieldErrors: Record<string, string>;
  readonly generalError: string | null;
}

const GENERIC_FALLBACK = "Something went wrong. Please try again.";

export function feedbackFromError(error: unknown, fallback: string = GENERIC_FALLBACK): FormFeedback {
  if (!(error instanceof ApiError)) {
    return { fieldErrors: {}, generalError: fallback };
  }

  if (error.code === "VALIDATION_ERROR") {
    const fieldErrors: Record<string, string> = {};
    for (const detail of error.details) {
      if (detail.field) fieldErrors[detail.field] = detail.message;
    }
    return {
      fieldErrors,
      generalError:
        Object.keys(fieldErrors).length === 0 ? "Please check the form and try again." : null,
    };
  }

  return { fieldErrors: {}, generalError: error.message };
}
