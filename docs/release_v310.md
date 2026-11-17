# V3.10 发布记录（Multi-AI Collaboration Engine）

- 版本定位：**V3.10.0-MVP-COMPLETE**（功能完成，非生产就绪）
- 发布日期：2026-11-16
- 测试基线：`tests/ai_team` **594 passed**（Python 3.13.16 + pytest 9.2.0）
- 安全边界：**不含任何自动实盘交易接口**，不产生下单指令、不做仓位建议

## 1. 交付范围

| 类别 | 内容 |
|---|---|
| 核心模块 | `ai_team/config.py`、`task_manager.py`、`report_collector.py`、`cross_validator.py`、`debate_engine.py`、`consensus_engine.py`、`investment_committee.py`、`prompt_library.py`、`schema_validator.py`、`research_pipeline.py` |
| 提示词 | `ai_team/prompts/` 四份：`cio_chatgpt.txt`、`intelligence_grok.txt`、`analyst_hark.txt`、`general_team.txt` |
| 数据契约 | `ai_team/schemas/` 五份：`agent_task`、`agent_report`、`debate_record`、`consensus_result`、`investment_decision` |
| 入口 | `main_v310.py`（CLI）+ `python -m ai_team.research_pipeline` |
| 测试 | `tests/ai_team/` 十一个测试文件，含 `test_integration_v310.py` 与 `test_research_pipeline.py` |
| 文档 | `docs/ai_team.md`（机制与接口）、本文件（发布与验收）、`docs/architecture.md`（增补指引） |

## 2. 十步实现清单

| 步骤 | 内容 | 证据 |
|---|---|---|
| 1 | 团队配置与角色定义 | `ai_team/config.py` + `tests/ai_team/test_config.py` |
| 2 | 任务创建、派发与状态流转 | `ai_team/task_manager.py` + `test_task_manager.py` |
| 3 | 多助手报告收集 | `ai_team/report_collector.py` + `test_report_collector.py` |
| 4 | 交叉校验 | `ai_team/cross_validator.py` + `test_cross_validator.py` |
| 5 | 多 AI 辩论 | `ai_team/debate_engine.py` + `test_debate_engine.py` |
| 6 | 共识引擎 | `ai_team/consensus_engine.py` + `test_consensus_engine.py` |
| 7 | 投资委员会 | `ai_team/investment_committee.py` + `test_investment_committee.py` |
| 8 | 角色专用提示词 | `ai_team/prompt_library.py` + `prompts/*.txt` + `test_prompt_library.py` |
| 9 | 统一 JSON Schema | `ai_team/schema_validator.py` + `schemas/*.schema.json` + `test_schema_validator.py` |
| 10 | 集成与验收 | `tests/ai_team/test_integration_v310.py` + `test_research_pipeline.py` |

## 3. 真实运行案例（非 Mock）

| 项目 | 值 |
|---|---|
| 标的 | `300394.SZ`（苏州天孚光通信，创业板） |
| 日期 | 2026-11-16 |
| 参与者 | ChatGPT（CIO）、Grok（市场情报）、Hark（基本面） |
| 报告 | `research/300394_2026-11-16/reports/{chatgpt,grok,hark}.md`，各含 7 个必填小节 |
| 各自置信度 | ChatGPT 0.88、Grok 0.72、Hark 0.68 |
| 辩论 | `debate.json`：chatgpt `clarify`、grok `support`、hark `clarify`；结论 `partial_consensus` |
| 投票 | `ballots.json`：6 席全部 `approve_with_conditions` |
| 决议 | `decision.json`：`approved_with_conditions`，`approval_score=1.0`，`quorum_met=true`，`veto_decisive=false`，6 条附条件 |
| 数据来路 | 三份报告由三个 AI 助手各自检索产出；**本机未独立核验**，落地前须以巨潮/交易所原文复核 |

复现命令：

```powershell
python main_v310.py `
  --symbol 300394 `
  --reports-dir research\300394_2026-11-16\reports `
  --debate research\300394_2026-11-16\debate.json `
  --ballots research\300394_2026-11-16\ballots.json `
  --output research\300394_2026-11-16\decision.json `
  --project-root research\300394_2026-11-16
```

## 4. Mock 测试与真实运行的区分

| 类型 | 位置 | 特征 |
|---|---|---|
| 单元 / 集成测试（Mock 数据） | `tests/ai_team/` | 报告正文与辩论内容均为构造样本；不联网、不调用真实 AI |
| 真实运行记录 | `research/300394_2026-11-16/` | 内容来自三个 AI 助手的真实检索；保留原始报告、辩论、投票与决议 |
| 流水线容错测试 | `tests/ai_team/test_research_pipeline.py` | 用 monkeypatch 模拟超时、瞬时失败、持续失败，验证重试与降级 |

## 5. 本轮新增/修复

| 变更 | 说明 |
|---|---|
| `research_pipeline` 容错 | 新增 `RetryPolicy`（重试次数 + 单次超时）、`AgentTimeoutError`、`InsufficientAgentsError`、`failed_agents` 审计字段 |
| 降级开关 | `--allow-missing-agents`：缺员时默认抛错，显式开启才降级继续 |
| 新增入口 | `main_v310.py` |
| 包级公开 API | `ai_team/__init__.py` 改为惰性导出（PEP 562），22 个公开符号，避免循环导入 |
| 文档 | 新增 `docs/ai_team.md`、本文件；`README.md` 升级到 V3.10；`docs/architecture.md` 增加增补指引 |

## 6. 已知限制

1. 弃权票仍计入 `approval_score` 分母（弃权≈半个反对），但已强制披露 `abstain_count` / `abstain_weight` / `abstain_rate` / `vote_breakdown`（2026-11-17 决策，见 `docs/v310_committee_audit.md` 第 5 节）。
2. required 委员被 disable 后**不再降门槛、不再免到场**：决议强制 `DEFERRED`，`required_members_met=False`（同上）。
3. 默认 `timeout_mode="thread"` 仍无法强杀被卡线程；需要硬终止时显式切换 `process`（spawn 子进程，可 terminate/kill，但要求 callable 可 pickle，且调用方脚本需带 `if __name__ == "__main__"` 保护）。详见 `docs/v310_hard_timeout.md`。
4. 流水线级产物（异议 / 共识 / 决议 JSON、`generation.json`）无跨进程互斥，同一 `project_root` 并发跑完整流水线仍需外部串行化；任务文件与报告提交已加锁（见第 8 节「并发写入加锁」）。
5. 票源映射为「一位助手 → 两个委员席位」，属研究治理记账，不是真实 6 人投委会。`CommitteeBallot` 已支持 `agent_id` / `report_id`，显式提供时同一助手不得投多票，可从决议追溯到来源；不提供时行为与旧版一致（向后兼容）。
6. 报告数据未做第三方核验，合规与投资判断需人工复核。`verified` 只是提交方声明，系统不抓取原始链接、不比对内容。

## 7. 验收清单（发布前逐项确认）

- [x] `pytest tests/ai_team -q` 全绿（650 passed，含 `test_hard_timeout.py` 4 例、`test_task_concurrency.py` 2 例、`test_report_concurrency.py` 2 例、`test_public_api.py` 3 例、`test_evidence_contract.py` 6 例、`test_source_extraction.py` 6 例、`test_sources_wiring.py` 4 例、`TestCommitteeEvidenceAudit` 3 例、`TestCommitteeGovernanceTightening` 5 例）
- [x] 十步模块与测试一一对应
- [x] 一条真实链路跑通并留下完整产物
- [x] 缺员 / 超时 / 瞬时失败三类容错有测试覆盖
- [x] 无实盘下单接口（`place_order` / `live_trade` / `broker_order` 命中 0）
- [x] README、`docs/ai_team.md`、发布记录齐备
- [x] 连续 20 次端到端场景压测（`python scripts/stress_v310_e2e.py --iterations 20` 实测 **40/40 passed（11.4s）**，含研究链路与进化续跑各 20 次）
- [x] 全仓基线测试复跑（2026-11-17 完成，见 7.1）
- [ ] 3 个 chromadb 依赖用例未执行（本机 `onnxruntime` 原生崩溃，属环境限制，见 7.1）

### 7.1 全仓基线复跑结果（2026-11-17）

环境：`%TEMP%\v310venv2`（Python 3.13），补齐 24 个缺失依赖后执行。

- 顶层 `tests/test_*.py`：**761 passed**（40 个文件全绿；`test_v09` 12 例、`test_v11` 8 例、`test_v21` 14 例为剔除 chromadb 用例后的计数）
- `tests/ai_team`：**650 passed**（治理收紧后新增 5 例）
- 合计 **1411 passed**
- 复跑过程修掉的三个真实缺陷：
  1. `backtest/metrics.py` 只 `import numpy as np`，第 51 行签名用 `pd.Series`，无 `from __future__ import annotations`，import 即 `NameError`，阻断 `test_v05.py` / `test_v12.py` → 补 `import pandas as pd`。
  2. akshare 1.20.46 把 `stock_zh_a_hist` 改名为 `stock_zh_a_hist_em` 且模块 `__getattr__` 对旧名抛 `AttributeError`；仓库在 `requirements.txt` 声明 `akshare>=1.18,<2` 覆盖了这次改名。新增 `data/akshare_compat.py`（惰性解析 `stock_zh_a_hist_em` → `stock_zh_a_hist`，导入阶段不解析），`data/akshare_client.py`、`data/market_data.py`、`data/historical.py`、`data_engine/akshare_loader.py`、`tools/market_tool.py` 统一改走 `_ak_hist`；`tests/test_v36.py`、`tests/test_v18.py` 打桩目标同步改为各模块自己的 `_ak_hist`。
  3. `tests/test_v27.py` 两个 PyTorch 用例直接 `import torch`，torch 不可用（缺失或 DLL 加载失败）时是 FAILED 而非 SKIPPED → 改为模块级 `try/except (ImportError, OSError)` + 用例内 `pytest.skip`。
- 仍是环境限制、无法用代码修掉的两处：
  - `onnxruntime` 在本机基座 Python 上 `import` 即原生崩溃（退出码 `-1073741819` / `0xC0000005`，`--upgrade` 到 1.32.0 后依旧），chromadb 默认嵌入函数依赖它。受影响用例 3 个：`test_v09.py::TestMemory::test_memory_save_search`、`test_v11.py::test_chromadb_vector_store`、`test_v21.py::TestVectorMemory::test_save_and_search`，故用 `--deselect` 剔除后取计数。
  - `torch` 在本机装出的 DLL 均为 1 字节且 `import torch` 报 `WinError 126 (shm.dll)`，已卸载；对应 2 个形状用例走 SKIP。

### 7.2 真实 API live 验收实测（2026-11-17）

`V310ResearchPipeline.run_live()` 是现成的真实链路入口，本轮直接用它做了一次 live 冒烟（标的 `300394.SZ`，`as_of_date=2026-11-17`）。四条实测结论：

1. **修掉一个静默失败缺陷**：`ai_team/adapters.py::load_env_file` 原先用 `encoding="utf-8"` 读取 `.env`。Windows 记事本保存的 `.env` 带 UTF-8 BOM（`EF BB BF`），首行键会变成 `"\ufeffOPENAI_API_KEY"`，被 `isalnum()` 校验挡掉后**静默丢弃**，于是 `build_registry()` 报 `missing: OPENAI_API_KEY` —— 即使 key 已经填好，live 模式也永远启动不了。改为 `encoding="utf-8-sig"` 后 `build_registry()` 正确返回 `available: ['chatgpt']`。新增 `tests/ai_team/test_env_file.py`（2 例，BOM / 无 BOM）锁定该行为。
2. **网络需要代理**：本机直连 `api.openai.com` 是 `WinError 10060`（连接超时），首轮 live 因此 0 份报告、`generation.json` 记录 `AdapterResponseError: network error`。设 `HTTPS_PROXY=http://127.0.0.1:7897` 后同一地址返回 401（未带鉴权头），说明链路已通。**live 运行必须先设代理**，否则表现为「模型没产出」，极易被误判成提示词或解析问题。
3. **单模型在结构上过不了校验**：`CrossValidator.__init__` 硬性要求 `min_reports >= 2`，`V310ResearchPipeline(min_reports=1)` 直接抛 `ValueError: min_reports must be at least 2.`。也就是说只有 OpenAI 一席时，`validate()` 必然失败（`InsufficientReportsError`）。这不是 bug，而是「多 AI 协作」的下限设计；单席位只能停在 `reports_collected`，`run_live` 也已对此显式返回该阶段状态而不伪造辩论与投票。
4. **因此 live 全链路验收的充要条件是「≥2 个真实席位」**：一是补 `XAI_API_KEY` / `XAI_MODEL` 让 Grok 上桌；二是走 hybrid——ChatGPT 走 API、Hark 走人工报告导入（Hark 未提供可当模型后端的 API，仓库 `.env.example` 与 Hark 自身答复一致）。两条路径都未在 evidence 上做过真实样本验收，故本轮仍标记为未完成。

## 8. 遗留待办（非 V3.10 范围）

- **V3.9.3 断点续跑**：已完成（2026-11-16）。新增 `restore_state()` / `save_checkpoint()` / `from_checkpoint()`、4 个 `Checkpoint*` 异常、`FitnessResult.from_dict()`，并对 checkpoint 与 JSONL 历史做代际一致性校验（`strict=True` 抛错 / 非 strict 写入 `run_metadata`）。详见 `docs/v393_checkpoint.md`，回归 `7 passed`。
- **P3 并发与压测**：已完成（2026-11-16）。`evolution/file_lock.py` 跨进程锁接入历史读写与 checkpoint 保存，并发回归 `4 passed`；`scripts/stress_v310_e2e.py --iterations 20` 实测 **40/40 passed（7.2s）**。详见 `docs/v393_p3.md`。
- **进程级硬超时**：已完成（2026-11-16）。`RetryPolicy` 新增 `timeout_mode`（`thread` / `process`），`process` 分支用 `multiprocessing.get_context("spawn")` + `Pipe(duplex=False)` 执行，超时后 `_terminate_process` 依次 `terminate()` → `join(1s)` → `kill()` → `join()`，被卡调用不再残留。不可 pickle 的 callable / 子进程启动失败抛 `HardTimeoutNotSupportedError`，不静默退回线程。`_submit_one` 的 lambda 改为可跨进程传递的 `_ReportCollectorCall`。新增 `tests/ai_team/test_hard_timeout.py`（4 例，`4 passed`），全量 `tests/ai_team` **626 passed**，evolution 四文件 **61 passed**；`submit_reports(timeout_mode="process")` 真实链路实测 3/3 报告落盘。详见 `docs/v310_hard_timeout.md`。
- **并发写入加锁**：已完成（2026-11-16）。`TaskManager` 复用 `evolution/file_lock.py` 的 `FileLock`：`_save_task_unlocked` 用 uuid 临时名 + `open("x")` + `flush` + `replace` 原子落盘，`_save_task` 外层持锁，新增 `_edit_task` 上下文管理器把「读盘 → 修改 → 写回 → 更新内存缓存」做成一个跨进程事务；`assign_task` / `update_status` / `start_task` / `submit_agent_report` 全部改为事务写法，`start_task` 在同一事务内同时推进任务与全部 assignment。`ReportCollector.collect_report` 在 `storage_dir/_locks/report_<sha256(task_id+agent_id)[:16]>.lock` 上加锁，内部逻辑拆为 `_collect_report_unlocked`，并发输家统一得到 `DuplicateReportError`（含把 `submit_agent_report` 的 `InvalidTaskTransitionError` 映射过去）。新增 `tests/ai_team/test_task_concurrency.py`（2 例）与 `tests/ai_team/test_report_concurrency.py`（2 例，spawn 多进程），全量 **626 passed**。详见 `docs/v310_concurrency.md`。
- **报告证据可追溯性契约**：已完成（2026-11-16）。`agent_report.schema.json` 的 `sources` 增加 `data_period` / `source_type` / `verification_status` / `verification_note` 四个可选字段；四个提示词追加统一的《结构化证据与可追溯性要求》；新增 `ai_team/evidence_contract.py` 的 `validate_evidence_contract()`（缺来源、缺链接、缺发布日期、缺数据期间、来源类型非法、核实状态缺失均给出稳定错误码，`unverified` 合法但必须显式标记）；`collect_report` 新增 `sources` 参数，传入时严格校验并把结果写入元数据 `validation["evidence_contract"]`，未传时记 `sources_not_provided` 以兼容旧调用。新增 `tests/ai_team/test_evidence_contract.py`（6 例），全量 **632 passed**。详见 `docs/v310_evidence_contract.md`。
- **结构化来源接线**：已完成（2026-11-17）。新增 `ai_team/source_extraction.py` 从模型正文提取 `sources`（fenced JSON / 裸对象 / 裸数组，取最后一个成功解析的块，失败一律返回 `None` 不抛异常，不使用递归正则）；`GeneratedReport` 与 `AgentReport` 增加 `sources` 字段，`generate_reports` 提取、`_submit_one` 透传、`run_with_adapters` 转换处一并带上，使真实 API 链路的来源真正进入 `collect_report` 校验。新增 `test_source_extraction.py`（6 例）与 `test_sources_wiring.py`（2 例），全量 **640 passed**；20 次端到端压测仍为 40/40（9.4s）。
- **证据状态进入投委会（只审计、不投票）**：已完成（2026-11-17）。`InvestmentCommittee.convene` / `_calculate_decision` 增加可选 `evidence_contract`，结果只写入 `CommitteeDecision.metadata["evidence_contract"]`（`status` / `valid` / `source_count` / `verified_count` / `unverified_count` / `unverified_sources`；未传记 `not_provided`，非 Mapping 记 `invalid_payload`），完全不参与 `status`、`approval_score`、`quorum`、`veto` 的计算。`ResearchPipeline._aggregate_evidence_contract()` 把多份报告的证据契约合并成一份（`validated` / `partial` / `not_provided`），`run()` 与 `run_with_adapters()` 均传给 `convene()`。新增 `TestCommitteeEvidenceAudit` 3 例 + 汇总函数 2 例，全量 **645 passed**，evolution 61 passed，压测 40/40（9.6s）。详见 `docs/v310_committee_audit.md` 第 6 节。


