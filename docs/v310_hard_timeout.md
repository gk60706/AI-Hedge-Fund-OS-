# V3.10 进程级硬超时（P3 收尾）

## 1. 问题

V3.10 的 `V310ResearchPipeline._call_with_timeout()` 原先只有线程实现：把一次报告提交丢进 `ThreadPoolExecutor`，用 `future.result(timeout=...)` 等结果。超时确实会抛 `AgentTimeoutError`，但 Python 没有办法从外部终止一个正在跑的线程，被卡住的调用会一直占用解释器资源，直到自己返回。

要让「超时」等于「真正终止」，唯一的办法是把这次调用放到一个可以 `kill` 的操作系统进程里。代价是跨进程只能传递可 pickle 的数据。

## 2. 设计

`RetryPolicy` 新增一个字段：

```python
@dataclass
class RetryPolicy:
    attempts: int = 2
    timeout_seconds: float | None = None
    timeout_mode: str = "thread"   # "thread" | "process"
```

`__post_init__` 校验 `attempts >= 1`、`timeout_seconds > 0`（允许 None）、`timeout_mode ∈ {"thread", "process"}`。

`_call_with_timeout(func, timeout_seconds, description, timeout_mode="thread")` 保持 `@staticmethod`：

- `timeout_seconds is None`：直接同步执行，不引入任何线程/进程。
- `thread`：保留原行为，超时抛 `AgentTimeoutError(... (thread abandoned))`；`finally` 用 `executor.shutdown(wait=False, cancel_futures=True)`，不再用 `with` 块等待卡住的线程。
- `process`：交给 `_call_with_process_timeout()`。

## 3. 进程分支的工作方式

```text
父进程                                   spawn 子进程
  |  pickle.dumps(func) 预检                 |
  |  Pipe(duplex=False)                      |
  |  Process(target=_hard_timeout_worker) -> |
  |  close(send_end)                         |  result = func()
  |  recv.poll(timeout)                      |  pickle.dumps(result) 预检
  |                                          |  send(("result"/"unsupported"/"error", ...))
  |  超时 -> terminate() -> join(1s)          |
  |        -> kill()      -> join()          |
```

关键点：

1. **可 pickle 预检**：`pickle.dumps(func)` 失败则直接抛 `HardTimeoutNotSupportedError`，不做「悄悄退回线程」的降级——同一份 `RetryPolicy` 在两种环境下语义必须一致。
2. **返回值预检**：子进程返回前也 `pickle.dumps` 一次，不可序列化的结果按 `unsupported` 回传并转成 `HardTimeoutNotSupportedError`。
3. **回传协议**：三元组 `(status, value, message)`。`error` 分支按异常类型名重建常见内建异常（`RuntimeError` / `ValueError` / `TypeError` / `KeyError` / `AssertionError` / `TimeoutError` / `AgentTimeoutError`），未知类型统一 `RuntimeError("Worker raised X: msg")`。
4. **终止顺序**：`terminate()` → `join(1s)` → 仍存活则 `kill()` → `join(1s)` → `join()`，并在 `finally` 里关闭两端 `Pipe` 与 `Process`，避免僵尸进程和句柄泄漏。
5. **父进程先关发送端**：`Pipe(duplex=False)` 下父进程持有写端会拖住 EOF 判定，所以 `start()` 后立刻 `send_connection.close()`。
6. **`_submit_one` 的 lambda 换成 `_ReportCollectorCall`**：`lambda` 无法被 pickle，改为一个 `@dataclass` 包装 `collector` + `kwargs`，`__call__` 里调 `collector.collect_report(**kwargs)`。`ReportCollector` 的字段（`task_manager`、`storage_dir: Path`、`required_sections: tuple`、`strict_validation: bool`）都可序列化。

## 4. 使用方式

```python
from ai_team.research_pipeline import RetryPolicy, V310ResearchPipeline

pipeline = V310ResearchPipeline(project_root=root)
pipeline.start_task("300394.SZ")

records = pipeline.submit_reports(
    reports,
    retry_policy=RetryPolicy(attempts=1, timeout_seconds=30, timeout_mode="process"),
)
```

命令行：

```powershell
python -m ai_team.research_pipeline --symbol 300394 `
  --reports-dir research\300394_2026-11-16\reports `
  --debate research\300394_2026-11-16\debate.json `
  --timeout-seconds 90 `
  --timeout-mode process
```

## 5. 约束（必须知道）

- **spawn 的 `__main__` 约束**：Windows 上 `spawn` 会重新导入主模块。调用方脚本必须写 `if __name__ == "__main__":` 保护，否则子进程启动时抛 `RuntimeError: An attempt has been made to start a new process before the current process has finished its bootstrapping phase`，本流水线会把它转成 `HardTimeoutNotSupportedError`。`pytest` 与包内 CLI 不受影响（实测通过）。
- **只接受模块级可调用对象或可 pickle 实例**：`lambda`、闭包、绑定到不可序列化对象的方法都会在预检阶段被拒。
- **成本**：每次提交都是一次进程创建 + 一次模块导入，比线程贵一到两个数量级。`process` 适合「必须能强杀」的长调用（如外部 AI API），不适合高频短调用。
- **返回值必须可 pickle**：报告记录是 dataclass/dict，满足；若未来引入不可序列化的对象（如打开的文件句柄），会按不支持处理。
- **平台差异**：Linux 上同样走 `spawn`（显式指定），保持与 Windows 一致的行为；不用 `fork` 是为了避免继承父进程的线程与锁状态。

## 6. 测试与验收

新增 `tests/ai_team/test_hard_timeout.py`，4 例：

| 测试 | 断言 |
|---|---|
| `test_process_timeout_terminates_slow_callable` | 1s 超时下抛 `AgentTimeoutError`，总耗时 < 2.5s，`multiprocessing.active_children()` 无存活子进程 |
| `test_process_mode_returns_normal_result` | 正常 callable 的 dict 原样返回 |
| `test_process_mode_propagates_runtime_error` | 子进程内 `RuntimeError("simulated worker failure")` 在父进程按类型重建 |
| `test_process_mode_rejects_unpickleable_callable` | `lambda` 触发 `HardTimeoutNotSupportedError` |

实测结果（2026-11-16，Windows，Python 3.13.16，pytest 9.2.0）：

```text
pytest tests/ai_team/test_hard_timeout.py -q     -> 4 passed in 5.15s
pytest tests/ai_team -q                          -> 619 passed in 22.69s   （基线 615 + 4）
evolution 四文件回归                              -> 61 passed in 19.69s    （与基线一致）
```

真实链路验证（带 `if __name__ == "__main__"` 保护的脚本）：

```text
submit_reports(..., RetryPolicy(attempts=1, timeout_seconds=30, timeout_mode="process"))
-> OK 3 ['chatgpt', 'grok', 'hark']
```

即 `ReportCollector` 跨进程 pickle、子进程落盘报告、父进程收集三条路径都跑通。

## 7. 明确没做的事

- 没有把 `timeout_mode` 的默认值改成 `process`：默认仍为 `thread`，避免改变既有调用方行为与成本模型。
- 没有为「线程模式超时后线程仍在跑」加资源回收：Python 做不到，文档已写明。
- 没有做进程池复用：每次调用独立进程，换取「一定杀得掉」的确定性。
- 没有接入真实外部 API：`--live` 仍受 API key 缺失限制，本轮验证的是本地 callable 与报告落盘链路。
