/** Public surface of the task dependencies feature. */

export { TaskDependenciesSection } from "./components/task-dependencies";
export { loadTaskDependencies, type TaskDependenciesData } from "./api/task-dependencies-data";
export { fetchDependencies } from "./api/dependency-queries";
export { addBlocker, removeBlocker } from "./api/dependency-mutations";
