/** Public surface of the labels feature. */

export { DeleteLabelButton } from "./components/delete-label-button";
export { LabelChip, LabelChips, LabelDot } from "./components/label-chip";
export { LabelFormDialog } from "./components/label-form-dialog";
export { LabelTable } from "./components/label-table";
export { LabelsScreen } from "./components/labels-screen";
export { fetchLabel, fetchLabels } from "./api/label-queries";
export {
  createLabel,
  deleteLabel,
  isLabelConflict,
  isLabelNameInUse,
  updateLabel,
} from "./api/label-mutations";
export {
  LABEL_COLORS,
  LABEL_COLOR_NAMES,
  LABEL_NAME_MAX_LENGTH,
  MAX_LABELS_PER_TASK,
  labelTasksHref,
  sortLabels,
} from "./label-utils";
