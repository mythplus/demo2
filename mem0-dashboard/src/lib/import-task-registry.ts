/**
 * 全局导入任务注册表
 *
 * 用于追踪当前 JS 运行时中正在执行的导入任务。
 * 存储在 window 对象上，这样即使 React 组件卸载再重新挂载，
 * 也能判断导入任务是否仍在后台执行（区分 SPA 路由切换 vs 页面刷新）。
 *
 * - SPA 路由切换：组件卸载，但 JS 运行时不变，全局 Set 仍在 → 导入仍在执行
 * - 页面刷新/关闭：JS 运行时重置，全局 Set 清空 → 导入真的中断了
 */

const GLOBAL_KEY = "__IMPORT_TASK_REGISTRY__";

function getRegistry(): Set<string> {
  if (typeof window === "undefined") return new Set();
  if (!(window as any)[GLOBAL_KEY]) {
    (window as any)[GLOBAL_KEY] = new Set<string>();
  }
  return (window as any)[GLOBAL_KEY];
}

/** 注册一个正在执行的导入任务 */
export function registerImportTask(taskId: string): void {
  getRegistry().add(taskId);
}

/** 注销一个已完成的导入任务 */
export function unregisterImportTask(taskId: string): void {
  getRegistry().delete(taskId);
}

/** 检查某个导入任务是否仍在执行 */
export function isImportTaskRunning(taskId: string): boolean {
  return getRegistry().has(taskId);
}

/** 检查是否有任何导入任务正在执行 */
export function hasRunningImportTask(): boolean {
  return getRegistry().size > 0;
}
