/** Public surface of the comments feature. */

export { CommentCard } from "./components/comment-card";
export { CommentComposer } from "./components/comment-composer";
export { TaskDiscussion } from "./components/task-discussion";
export { fetchComments } from "./api/comment-queries";
export {
  addComment,
  deleteComment,
  editComment,
  isCommentForbidden,
} from "./api/comment-mutations";
export { loadTaskDiscussion } from "./api/task-discussion-data";
export type { TaskDiscussionData } from "./api/task-discussion-data";
export { COMMENT_MAX_LENGTH } from "./comment-utils";
