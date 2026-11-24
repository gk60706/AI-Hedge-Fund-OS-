# Changelog

本项目的所有重要变更都记录在本文件中。格式参考 Keep a Changelog。

## [Unreleased]

### Added
- `configs/ai_providers.colab.yaml` 与 `docs/colab_endpoint.md`：把 Colab 免费 T4 上的 OpenAI 兼容端点当作验收席位，用真实 HTTP 跑通 `--live --providers-file`。
- `tests/ai_team/test_pipeline_degraded.py`：显式降级路径的回归测试（零报告、单份不完整报告、严格模式不变）。

### Fixed
- `run_live` 在 `--allow-missing-agents` 且报告数不足 `min_reports` 时不再崩溃（原先 `validate()` 抛 `InsufficientReportsError`，退出码 1），改为返回 `stage=degraded_no_reports|degraded_insufficient_reports` 并落盘 `reports/degraded.json`。
- `_submit_one` 的 `allow_incomplete` 与 `allow_missing` 联动：显式降级时允许缺章节报告入库并在 notes 追加 `incomplete=true`；默认仍是严格口径。

## [3.10.0] - 2026-11-18

### Added
- ai_team 的 14 个模块落地：任务、报告收集、交叉校验、辩论、共识、投委会、端到端流水线、真实 API 适配器。
- OpenAI 兼容适配器，支持 ChatGPT、Grok 和自建 Hark 网关。
- 结构化来源提取与证据契约校验。
- 交叉校验结果落盘为 `VAL-*.json`。
- RetryPolicy 支持 thread 和 process 两种超时模式；process 模式可以硬终止卡住的调用。
- 429 限流单独归类为 `AdapterRateLimitError`，并解析 `Retry-After`。
- 适配器配置边界校验（timeout / max_tokens / temperature / base_url）。
- live 调用次数与 token 预算上限。
- `scripts/smoke_live.py`：支持 `--task new/existing` 和 `--dry-run`，并支持用 `--import-report/--file` 人工导入报告。
- `pytest.ini`：登记 `live` 与 `slow` 两个 marker。
- 新增 `ai_team/providers.py` 与 `configs/ai_providers.yaml`：用 YAML 自定义任意多家 OpenAI 兼容大模型（内置 DeepSeek / Kimi / Qwen / 智谱 / MiniMax / 硅基流动 / OpenRouter / Groq / xAI / 自建网关模板）；支持 `${VAR:-默认值}` 展开；缺 key 的厂商记为 skipped；输出中不含密钥。
- `research_pipeline` 新增 `--providers-file` 参数；新增离线自检命令 `python -m ai_team.providers list/check`。

### Changed
- 没有来源的报告不再计入投票或共识，统一标记为 `seats_unsourced`。
- 缺 key 的席位记为 skipped 并给出原因，不再静默跳过。
- 密钥不再写入日志和产物。
- pytest 默认只跑 `tests` 目录，并默认跳过 live 用例（`-m "not live"`）。

### Fixed
- 任务、报告、历史三类产物改为原子写加跨进程文件锁，并发写入不再互相覆盖。
- 429 重试改为有上限的退避，避免无限重试。
- 两个同名的 `test_config.py` 整套运行时会冲突，现固定使用 `--import-mode=importlib`。
- `test_v21` 引用了仓库里不存在的 `memory.vector_memory`，改为调用真实的 `brain.memory` 接口。
