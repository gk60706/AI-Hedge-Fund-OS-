# 桌面客户端构建与验收记录（V3.10）

本文件记录 Windows exe 的实际构建方式、踩过的坑和验证结果，供后续复现使用。

## 1. 环境

- Python 3.13（本机 venv：`%TEMP%\v310venv2`）
- 依赖：`fastapi`、`uvicorn`、`PyYAML`、`pyinstaller>=6.11`、`pywebview`
- 不安装 pandas / numpy / torch / chromadb / akshare / sklearn / matplotlib：`ai_team` 只依赖标准库 + PyYAML，装上反而让包体膨胀并引入崩溃风险

## 2. 构建

```powershell
# 必须在仓库根执行，且 spec 用绝对路径（相对路径会让 SPECPATH 层级算错）
& $py -m PyInstaller --noconfirm --clean --log-level WARN "C:\...\股票分析\desktop\app.spec"

# 产物：dist\AIHedgeFundOS\（约 52 MB）
# 首次运行前把配置放到 exe 同级
Copy-Item -Recurse -Force configs dist\AIHedgeFundOS\configs
```

## 3. 运行时的路径约定

- 冻结态下 `PROJECT_ROOT` = exe 所在目录，不是仓库根
- 因此 `configs/`、`reports/`、`research/` 都相对 exe 目录：
  - `configs/ai_providers.yaml` 必须复制到 exe 同级
  - 研究产物写到 `dist\AIHedgeFundOS\reports\`
  - 「文件」列表看不到仓库根的历史报告，需要时手工复制 `reports/` 过去
- 日志：`aihedgefundos.log`（exe 同级，追加写）

## 4. 已修的三个坑

1. **spec 路径层级**：`ROOT = Path(SPECPATH).resolve().parent`（原来写成 `parent.parent`，把仓库根算成了桌面目录，报 `script 'C:\Users\Administrator\Desktop\desktop\launcher.py' not found`）。
2. **windowed 下 `print` 崩溃**：`console=False` 时 `sys.stdout` 为 `None`，launcher 里的 `print` 抛 `AttributeError`，进程启动即退出。已改为写日志文件。
3. **windowed 下 uvicorn 日志崩溃**：uvicorn 默认 `LOGGING_CONFIG` 在 `configure_logging` 里访问 `sys.stderr.isatty()`，得 `AttributeError: 'NoneType' object has no attribute 'isatty'` → `ValueError: Unable to configure formatter 'default'`。已改为 `uvicorn.Config(..., log_config=None)`。

## 5. 验收记录（2026-11-18）

- `dist\AIHedgeFundOS\AIHedgeFundOS.exe` 启动后进程存活，`MainWindowTitle = AI Hedge Fund OS V3.10`
- `GET /api/health` → `{"status":"ok","version":"3.10.0"}`（端口 8765）
- `GET /` → 200，14396 字节（ui.html）
- `GET /api/providers` → 11 条，`openai` 为 `skipped: missing: AIH_OPENAI_API_KEY`
- `POST /api/research`（无 key、allow_missing）→ 任务 `done`，`stage: degraded_no_reports`、`reports_collected: 0`
- 打包体积 52.4 MB（onedir），构建耗时约 90 秒

## 6. 仍未覆盖

- 没有 `pywebview` 时的兜底是打开系统默认浏览器；本机已装 pywebview，走的是窗口模式
- 窗口在远程/锁屏会话下可能不可见，但进程与窗口句柄存在
- 不含行情采集、筛选、回测、因子模块：这些依赖 pandas/numpy/akshare/backtrader，未打包
- 真实研究需要 provider API key；当前仓库 `.env` 无可用 key，只能用 `degraded_*` 路径验收
- 任务状态只在内存，关窗即丢
