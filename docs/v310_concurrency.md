# V3.10 并发写入加锁

## 1. 问题

V3.10 的任务与报告都落成单个 JSON / Markdown 文件，但写入路径存在两类并发缺陷：

1. `TaskManager._save_task()` 用固定临时名 `task.json.tmp` 再 `replace`，两个进程同时保存同一任务会在同一个临时文件上互踩；
2. 读取 → 修改 → 写回之间没有互斥，多个进程各自基于旧快照写回，后写覆盖先写（lost update）；
3. `ReportCollector.collect_report()` 先扫 `_metadata` 做重复提交判定，再写 `<report>.md` 与 `<meta>.json`，判定与写入之间没有互斥，同一任务同一 agent 的并发提交可能都通过判定。

单文件本身是原子替换（uuid 临时名），缺的是「判定 + 写入」这一段的串行化。

## 2. 设计

复用 `evolution/file_lock.py` 的 `FileLock`（Windows `msvcrt.locking` / POSIX `fcntl.flock`，侧车 `<name>.lock`，默认 `timeout=10s`、`poll_interval=0.05s`）。`evolution/__init__.py` 为空，跨包导入不会拉入 numpy / pandas。

### 2.1 任务文件锁

粒度：单个任务文件（`storage_dir/<task_id>.json` 的侧车锁）。

- `_save_task_unlocked(task)`：调用方必须已持锁；临时名改为 `<stem>.<uuid>.tmp`，用 `open("x")` 防重名、`flush()` 后 `replace()`，失败清理临时文件并抛 `TaskPersistenceError`；
- `_save_task(task)`：独立保存入口，`with FileLock(path)` 后调 `unlocked` 版本；
- `_edit_task(task_id)`：`@contextmanager`，持锁 → 从磁盘重新读 `ResearchTask.from_dict` → `yield task` → 写回 → 更新 `self._tasks[task_id]`。`FileNotFoundError` 映射为 `TaskNotFoundError`，其余读错误映射为 `TaskPersistenceError`。

改造为事务的方法：

| 方法 | 事务内做的事 |
| --- | --- |
| `assign_task` | 读盘 → 校验状态 / agent 合法性 → 重建 assignments → 置 `ASSIGNED` → 写回 |
| `update_status` | 读盘 → 校验状态迁移 → 置新状态 → 写回 |
| `start_task` | 读盘 → 校验迁移 → 置 `IN_PROGRESS` 且全部 assignment 置 `in_progress` → 写回（一次事务，不再分两次保存） |
| `submit_agent_report` | 读盘 → 校验任务状态 / 分配 / 重复提交 → 标记 assignment 与提交时间 → 全部提交则置 `SUBMITTED` → 写回 |

`create_task` 仍走 `_save_task`：新任务 ID 唯一，不存在与既有任务文件的冲突。

### 2.2 报告提交锁

粒度：`task_id + agent_id`。

- 锁文件：`storage_dir/_locks/report_<sha256(task_id\0agent_id)[:16]>.lock`；
- `collect_report` 只做参数规范化与锁键计算，随后持锁调用 `_collect_report_unlocked`（原有校验、重复判定、写 md、写 meta、调用 `task_manager.submit_agent_report` 的逻辑原样保留）；
- 同一任务同一 agent 串行，不同 agent 用不同锁文件，互不阻塞；
- 并发输家在拿到锁后重新判定，稳定得到 `DuplicateReportError`；为覆盖其它调用路径抢先完成提交的情况，`submit_agent_report` 抛出的 `InvalidTaskTransitionError` 也映射为 `DuplicateReportError`，不再被包成 `ReportCollectorError`。

锁顺序固定为「报告锁 → 任务锁」，代码中没有任何位置反向先拿任务锁再拿报告锁，因此不会形成锁环。

## 3. 与进程级硬超时共存

- 超时子进程内部才获取文件锁：父进程在 `_call_with_process_timeout` 等结果时不持有任何任务 / 报告锁，不会出现「父进程持锁等子进程、子进程等锁」的互等；
- 子进程被 `terminate()` / `kill()` 时，操作系统随进程退出释放 advisory lock；残留的 `.lock` 文件只是占位字节，不影响后续加锁（`FileLock.__enter__` 以 `a+b` 打开，不依赖文件是否已被删除）；
- 唯一代价：被强杀的子进程可能在「已写 md、未写 meta」之间中断，留下孤儿 Markdown。这与加锁前的失败窗口一致，`collect_report` 的清理逻辑只在同进程异常时生效。

## 4. 测试

| 文件 | 例数 | 覆盖 |
| --- | --- | --- |
| `tests/ai_team/test_task_concurrency.py` | 2 | 6 进程并发创建 12 个任务，JSON 全部可解析且 ID 与文件名一致；3 进程并发提交同一任务，最终状态自洽、3 个 assignment 都有 `submitted_at` |
| `tests/ai_team/test_report_concurrency.py` | 2 | 同任务同 agent 3 进程只 1 条落盘、其余 `DuplicateReportError`；不同 agent 3 进程全部成功，元数据与 Markdown 一一对应 |

两套测试都使用 `multiprocessing.get_context("spawn")` 与模块级 worker 函数，符合 Windows 要求。

实测：`pytest tests/ai_team -q` → **626 passed**；`evolution` 四文件 → **61 passed**。

## 5. 明确未做

- 流水线级产物（`objections.json`、`debate` / `consensus` / `committee` 结果、`generation.json`）没有加锁：同一 `project_root` 并发跑完整流水线仍是后写覆盖，需要上层串行化；
- 没有做锁的公平性 / 优先级，`FileLock` 是自旋 + 超时（10s），超时抛 `FileLockTimeoutError`；
- 没有做崩溃恢复：进程被强杀后可能留下孤儿 Markdown，需要人工或后续对账清理。
