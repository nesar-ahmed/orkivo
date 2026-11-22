/**
 * Typed domain contracts for labels, mirroring
 * backend/app/modules/labels/schemas.py.
 *
 * A label is a named, colored tag inside exactly one workspace; a task may carry
 * several. Names are unique per workspace regardless of case; deleting a label
 * takes it off every task, which stay in the workspace.
 */

/**
 * The palette a label is painted from (backend `LabelColor`). A name, not a hex
 * code: each maps onto a design token with a light and a dark variant.
 */
export type LabelColor =
  | "gray"
  | "red"
  | "orange"
  | "yellow"
  | "green"
  | "teal"
  | "blue"
  | "indigo"
  | "purple"
  | "pink";

/** Who created a label: a name to recognise, never an email. */
export interface LabelPerson {
  id: string;
  display_name: string;
}

export interface Label {
  id: string;
  workspace_id: string;
  name: string;
  color: LabelColor;
  /** Increments on every change. Send it back on update or delete. */
  version: number;
  /** `null` only if the account is gone. */
  created_by: LabelPerson | null;
  created_at: string;
  updated_at: string;
}

/** A label in its workspace's list, with how many tasks carry it. */
export interface LabelSummary extends Label {
  task_count: number;
}

/** Paginated collection envelope returned by GET /workspaces/{id}/labels. */
export interface LabelListResponse {
  items: LabelSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface LabelCreateInput {
  name: string;
  color?: LabelColor;
}

/**
 * PATCH payload: only provided fields are changed. `version` is the version the
 * client read; if a colleague saved since, the API answers 409 `LABEL_CONFLICT`.
 */
export type LabelUpdateInput = Partial<LabelCreateInput> & { version?: number };
