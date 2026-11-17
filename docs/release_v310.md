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
3. **单模型在结构上过不了校验**：本轮之前 `CrossValidator` 两处硬性要求 `min_reports >= 2`，`V310ResearchPipeline(min_reports=1)` 直接抛 `ValueError`，只有 OpenAI 一席时 `validate()` 必然失败（`InsufficientReportsError`）。**该契约本轮已按 Hark 的建议调整**：`min_reports` 下限放开到 1，单席位跑完后不再报错，而是返回 `status="not_performed"` 并附 `Multi-AI not performed: 1/3 seats reported.` 警告，绝不输出「多模型一致」；`min_reports=0` 仍直接拒绝。详见 7.4。
4. **因此 live 全链路验收的充要条件是「≥2 个真实席位」**：一是补 `XAI_API_KEY` / `XAI_MODEL` 让 Grok 上桌；二是走 hybrid——ChatGPT 走 API、Hark 走人工报告导入（Hark 未提供可当模型后端的 API，仓库 `.env.example` 与 Hark 自身答复一致）。两条路径都未在 evidence 上做过真实样本验收，故本轮仍标记为未完成。
5. **三个 API 席位当天全部不可用**（2026-11-17 实测）：`chatgpt` 的 key 有效但 `HTTP 429 insufficient_quota`（`credit_balance_exhausted`，账户无余额）；`grok` 免费版不提供 API key，传入的 36 位 UUID 被 xAI 判为 `Incorrect API key provided`；`hark` 本就不提供模型后端 API。结论：**V3.10 的「多 AI」在当前账号条件下只能靠人工席位成立**。
6. **人工席位链路已实测跑通**：`ReportCollector.collect_report(task_id, agent_id, content, source="manual")` 是现成的导入入口，`start_task` 默认给 `chatgpt / grok / hark` 三席都建 assignment，因此人工报告无需额外接线。实测 `TASK-20261117-1E0CC2F2` 依次导入三份真实报告（ChatGPT、Grok 各一份完整报告，Hark 一份在「Evidence and Sources」处被页面截断的残缺报告），`CrossValidator.validate_task()` 返回 `status=success`、`report_count=3`、`conflict_count=0`，三席 quality 分别 100 / 100 / 76，`hark` 因残缺被判 `incomplete` 并带 1 条 warning。证据见 `reports/hybrid_smoke/validation_3seats.json`。
7. **该次验收同时暴露两个产品级缺口**：`research_pipeline` 没有「续接既有 task_id」的公开入口（新进程里 `validate()` 直接抛 `RuntimeError: start_task must run before this stage`，只能用 `CrossValidator` 手工接），以及人工席位没有 CLI / 脚本化导入手段，只能写代码调用 `collect_report`。这两点正是三家 AI 都点名的 `scripts/smoke_live.py` 缺失的具体形态。
8. 本次导入的三份报告均为模型自述、数值未与交易所原始数据核对（`verification_status=verified` 只是模型自己声明），**不得当作投资结论使用**，仅作链路验收样本。

### 7.3 人工席位 CLI：`scripts/smoke_live.py`

第 7.2 节第 7 条点名的「人工席位没有 CLI」已补齐，代码取自 ChatGPT 会话（本轮多段输出拼接，含一处仓库级修复：`sys.path.insert` 对齐 `scripts/run_research.py` 约定，否则直接运行会 `ModuleNotFoundError: ai_team`）。

用途：把「导入人工报告 → 续接既有任务 → 交叉校验」固化成一条命令，不再需要手写 `collect_report` / `CrossValidator`。

```powershell
# 只校验既有任务（不导入）
python scripts\smoke_live.py --task-id TASK-20261117-1E0CC2F2 --artifact artifacts\smoke\run_existing.json

# 三席人工报告导入 + 校验（--import-report 与 --file 一一对应）
python scripts\smoke_live.py --task-id TASK-20261117-4CEEE3A1 `
  --import-report chatgpt --file report_chatgpt.md `
  --import-report grok    --file report_grok.md `
  --import-report hark    --file report_hark.md `
  --artifact artifacts\smoke\run_import.json
```

实测结果：

- 既有任务 `TASK-20261117-1E0CC2F2` → `report_count=3`、`status=success`、`VAL-20261117-7862E97D8D`，退出码 0。
- 新任务 `TASK-20261117-4CEEE3A1` 走完整导入路径 → 三席 `success`、`report_count=3`、`status=success`、`VAL-20261117-B0B74C5593`，退出码 0。
- 产物为 tmp + `os.replace` 原子写（`artifacts/smoke/run_*.json`），文件内不含密钥。

仍未覆盖：其他阶段（辩论 / 共识 / 投委会）在本机已可通过 `V310ResearchPipeline.resume(task_id)` 续接同一任务；该入口本轮已补齐（新建进程 `resume` 后 `validate()` 实测通过，见 `artifacts/smoke/run_resume.json`），CLI 也已从「直接构造 `CrossValidator`」改为走这条正式接口。

### 7.4 席位诚实披露（多 AI 只有一席时不能再叫「一致」）

三家 AI 交叉审计的共同结论是：单席位 / 缺席席位必须显式披露，不能靠「1 个模型说好」冒充「多 AI 协作」。本轮落地规则（代码由 ChatGPT 出稿）：

1. **`min_reports` 下限 1**：`CrossValidator.__init__` 与 `validate_task` 两处硬约束都从 `< 2` 改为 `< 1`，报错文案分别对齐到 `min_reports must be at least 1.` / `min_reports must be an integer >= 1.`；`0` 与非整数仍拒绝。
2. **低于 2 席即 `not_performed`**：`validate_task` 统计 `seats_active`（实际有报告的 `agent_id`）、`seats_assigned`（任务 assignment 的 `agent_id`）、`seats_missing`；当活跃席位 < 2 时把 `status` 覆盖为 `"not_performed"` 并追加 `Multi-AI not performed: N/M seats reported.`。这一判定放在原有 `SUCCESS` / `PARTIAL` 逻辑之后，只降级、不改写原判定。
3. **缺席席位逐一点名**：活跃席位 ≥ 2 但仍有席位未交报告时，追加 `Seats not reporting: grok, hark`。
4. **结果可审计**：`CrossValidationResult.metadata` 新增 `seats_active` / `seats_assigned` / `seats_missing` 三个列表，调用方不必再靠 warnings 猜席位。
5. **CLI 与流水线口径**：`V310ResearchPipeline` 默认仍为 `min_reports=2`（正式流水线要求 ≥2 席成立），单席位只在显式 `min_reports=1` 时出现，且必然带 `not_performed`。

测试：`tests/ai_team/test_cross_validator.py` 新增 `test_single_seat_marks_not_performed`（单席 `not_performed` + 警告前缀）、`test_missing_seat_is_disclosed`（两席 + `Seats not reporting` 警告），原 `test_min_reports_must_be_at_least_two` 按新契约改写为 `test_min_reports_must_be_at_least_one`（`min_reports=0` 拒绝），`test_validate_task_rejects_invalid_min_reports` 的入参由 `1` 改为 `0`。实测 `test_cross_validator.py` 94 passed，全量 `tests/ai_team` **657 passed, 4 subtests（39.45s）**。

### 7.5 无结构化来源的席位不计票

三家审计共同点名「零来源报告仍被当作有效票」。本轮按「不计票 + 不硬拒」的口径落地（代码由 ChatGPT 出稿）：

1. **来源状态来自证据契约**：`validate_task` 逐条读 `record.validation["evidence_contract"]["status"]`，只有 `validated` 才算「有结构化来源」，其余（`sources_not_provided` 等）进 `unsourced_ids`。
2. **混合场景只按有来源席位投票**：当有来源与无来源席位同时存在（`mixed`），`comparisons` 与 `consensus` 只使用有来源子集；整体 `evidence_score` 也只对该子集取平均。`conflicts` 仍用全部席位，缺来源不能把冲突藏起来。
3. **全无来源不伪造结论**：所有席位都没有结构化来源时，保持原有全量比对（否则任何历史任务都会变 partial），但强制追加 `No structured sources for any seat; agreement is model-self-reported.`，并在 `metadata["seats_unsourced"]` 列出全部席位。
4. **结果可审计**：`metadata` 新增 `seats_sourced` / `seats_unsourced`；混合场景追加 `Seats excluded from consensus (no structured sources): grok, hark`。
5. **CLI 侧打通来源提取**：`scripts/smoke_live.py` 导入人工报告时调用 `extract_sources_from_content()`，把解析到的来源传给 `collect_report(sources=...)`，并在产物里记 `sources_detected`；来源格式不合法（`InvalidReportError`）时**降级为无来源重试**，报告照常入库并记 `sources_invalid: true`，不再整份丢弃。另补 `--import-report` 与 `--file` 数量不等时显式 `return 2`（原先 `zip` 会静默截断）。

测试：新增 `test_unsourced_seats_are_excluded_from_consensus`（chatgpt 带合法来源、grok/hark 无来源 → `seats_sourced == ["chatgpt"]`、`seats_unsourced` 含 grok/hark、出现 `Seats excluded from consensus` 警告），`test_cross_validator.py` 95 passed，全量 `tests/ai_team` **658 passed, 4 subtests（42.43s）**。

**本轮真实链路实测又暴露一个契约缺口**（已修，见 7.6）：新建 `TASK-20261117-E9218E6D` 走 CLI 导入三份真实报告，`sources_detected` 三席全为 false —— ChatGPT 那份的 4 条来源本身是真实的（巨潮三季报 / 国泰海通点评 / 回购进展 / 中财网行情），但被证据契约拒绝：`published_at` 是日期（`2026-10-29`）不带时区，`source_type` 用了 `research_report` / `exchange_data` 这两个不在 `ALLOWED_SOURCE_TYPES` 里的写法。也就是说**契约比模型的实际输出更严，正确来源会被判成无来源**。

### 7.6 来源标准化：别名映射 + 日期精度

按「标准化而不是继续加严」修（代码由 ChatGPT 出稿），只放宽两处可确定的写法差异，不替模型编造任何信息：

1. **来源类型别名**：新增 `SOURCE_TYPE_ALIASES`，把模型常用的近义写法映射到白名单规范值 —— `research_report` / `broker_report` → `industry_research`，`exchange_data` / `market_data` → `financial_data`，`news` / `news_article` → `news_media`，`filing` / `company_announcement` → `company_filing`，`official_site` → `official`，`government_site` → `government`，`website` / `web` → `other`。校验时先做归一（`strip` + 小写 + 空格/连字符转下划线），命中白名单直接用，否则查别名表，两处都不中才报 `invalid_source_type`。
2. **发布日期精度**：原本只认「带 `T` 且带时区」的完整时间戳。现在额外接受纯日期 `YYYY-MM-DD`（`date.fromisoformat` 判定，合法即通过，**不补时分秒、不猜时区**）；带时间但缺时区的仍拒绝，失败文案改为「发布日期必须是带时区的 ISO 8601 时间戳，或 YYYY-MM-DD 日期精度。」

**同一条真实数据重放的对照**（同一批三份真实报告）：

| 项 | `TASK-20261117-E9218E6D`（标准化前） | `TASK-20261117-B7124A1F`（标准化后） |
| --- | --- | --- |
| ChatGPT 来源 | `sources_detected: false`，`sources_invalid: true` | `sources_detected: true`（4 条来源全部通过契约） |
| Grok 来源 | `sources_invalid: true`（URL 被拼接损坏，属真损坏） | 同前，仍 `sources_invalid: true` 并降级为无来源导入 |
| Hark 来源 | 无结构化来源 | 同前，无结构化来源 |
| 校验结果 | `success`（三席全无来源，只发模型自述警告） | **`partial`**（`VAL-20261117-E2031C0C27`，只有 ChatGPT 计入共识） |

即：契约放宽后，真实可用的 4 条来源第一次被正确识别，混合场景按「只有有来源的席位投票」执行，Grok 的损坏 URL 与 Hark 的无来源都被如实披露而不是整份丢弃。

测试：新增 `test_date_only_and_alias_source_types_are_accepted`（日期精度 + 连字符别名 `research-report` 必须通过），`test_evidence_contract.py` + `test_cross_validator.py` 合计 **102 passed**，全量 `tests/ai_team` **659 passed, 4 subtests**。

### 7.7 流水线产物：原子写 + 跨进程互斥

三家审计都点名「产物写入没有跨进程互斥，并发或中途崩溃会留下半截 JSON」。按「锁只加在真正的产物写入点」的口径修（代码由 ChatGPT 出稿），不动 `TaskManager` / `ReportCollector` 已有的锁：

1. **新增模块级辅助函数** `_write_text_atomic(path, text, *, timeout=30.0)`：父目录 `mkdir(parents=True, exist_ok=True)`，在 `FileLock(path, timeout)`（`evolution.file_lock`，目标文件旁的 `.lock` 侧车文件）内，用 `tempfile.mkstemp` 在**同目录**建临时文件，写入 UTF-8 后 `flush` + `os.fsync`，再 `os.replace` 覆盖目标；任一步失败都 `unlink` 临时文件，不留残片。
2. **三处裸写改为调用它**：`run_live` 的 `reports/<agent>.md`、`reports/generation.json`（审计记录），以及 `save_artifact()` 的结果 JSON。

**真实路径验证**（不依赖 API key，走真实 `run_live` 代码路径）：在临时目录跑 `run_live`，三席因无可用凭据全部失败、`submit_reports` 抛出 `InsufficientAgentsError`，但落盘已经完成 ——

- `generation.json` 存在且 1188 字节，`json.loads` 可解析，顶层键为 `task_id / symbol / as_of_date / registry / generated / failures`；
- 目录内**没有** `.generation.json.*` 形式的残留临时文件；
- 只有设计内的 `generation.json.lock` 侧车文件。

测试：新增 `test_atomic_write_leaves_no_temp_files`（内容正确 + 无点号开头残留），`test_research_pipeline.py` 10 passed，全量 `tests/ai_team` **660 passed, 4 subtests（37.92s）**。

## 8. 遗留待办（非 V3.10 范围）

- **V3.9.3 断点续跑**：已完成（2026-11-16）。新增 `restore_state()` / `save_checkpoint()` / `from_checkpoint()`、4 个 `Checkpoint*` 异常、`FitnessResult.from_dict()`，并对 checkpoint 与 JSONL 历史做代际一致性校验（`strict=True` 抛错 / 非 strict 写入 `run_metadata`）。详见 `docs/v393_checkpoint.md`，回归 `7 passed`。
- **P3 并发与压测**：已完成（2026-11-16）。`evolution/file_lock.py` 跨进程锁接入历史读写与 checkpoint 保存，并发回归 `4 passed`；`scripts/stress_v310_e2e.py --iterations 20` 实测 **40/40 passed（7.2s）**。详见 `docs/v393_p3.md`。
- **进程级硬超时**：已完成（2026-11-16）。`RetryPolicy` 新增 `timeout_mode`（`thread` / `process`），`process` 分支用 `multiprocessing.get_context("spawn")` + `Pipe(duplex=False)` 执行，超时后 `_terminate_process` 依次 `terminate()` → `join(1s)` → `kill()` → `join()`，被卡调用不再残留。不可 pickle 的 callable / 子进程启动失败抛 `HardTimeoutNotSupportedError`，不静默退回线程。`_submit_one` 的 lambda 改为可跨进程传递的 `_ReportCollectorCall`。新增 `tests/ai_team/test_hard_timeout.py`（4 例，`4 passed`），全量 `tests/ai_team` **626 passed**，evolution 四文件 **61 passed**；`submit_reports(timeout_mode="process")` 真实链路实测 3/3 报告落盘。详见 `docs/v310_hard_timeout.md`。
- **并发写入加锁**：已完成（2026-11-16）。`TaskManager` 复用 `evolution/file_lock.py` 的 `FileLock`：`_save_task_unlocked` 用 uuid 临时名 + `open("x")` + `flush` + `replace` 原子落盘，`_save_task` 外层持锁，新增 `_edit_task` 上下文管理器把「读盘 → 修改 → 写回 → 更新内存缓存」做成一个跨进程事务；`assign_task` / `update_status` / `start_task` / `submit_agent_report` 全部改为事务写法，`start_task` 在同一事务内同时推进任务与全部 assignment。`ReportCollector.collect_report` 在 `storage_dir/_locks/report_<sha256(task_id+agent_id)[:16]>.lock` 上加锁，内部逻辑拆为 `_collect_report_unlocked`，并发输家统一得到 `DuplicateReportError`（含把 `submit_agent_report` 的 `InvalidTaskTransitionError` 映射过去）。新增 `tests/ai_team/test_task_concurrency.py`（2 例）与 `tests/ai_team/test_report_concurrency.py`（2 例，spawn 多进程），全量 **626 passed**。详见 `docs/v310_concurrency.md`。
- **报告证据可追溯性契约**：已完成（2026-11-16）。`agent_report.schema.json` 的 `sources` 增加 `data_period` / `source_type` / `verification_status` / `verification_note` 四个可选字段；四个提示词追加统一的《结构化证据与可追溯性要求》；新增 `ai_team/evidence_contract.py` 的 `validate_evidence_contract()`（缺来源、缺链接、缺发布日期、缺数据期间、来源类型非法、核实状态缺失均给出稳定错误码，`unverified` 合法但必须显式标记）；`collect_report` 新增 `sources` 参数，传入时严格校验并把结果写入元数据 `validation["evidence_contract"]`，未传时记 `sources_not_provided` 以兼容旧调用。新增 `tests/ai_team/test_evidence_contract.py`（6 例），全量 **632 passed**。详见 `docs/v310_evidence_contract.md`。
- **结构化来源接线**：已完成（2026-11-17）。新增 `ai_team/source_extraction.py` 从模型正文提取 `sources`（fenced JSON / 裸对象 / 裸数组，取最后一个成功解析的块，失败一律返回 `None` 不抛异常，不使用递归正则）；`GeneratedReport` 与 `AgentReport` 增加 `sources` 字段，`generate_reports` 提取、`_submit_one` 透传、`run_with_adapters` 转换处一并带上，使真实 API 链路的来源真正进入 `collect_report` 校验。新增 `test_source_extraction.py`（6 例）与 `test_sources_wiring.py`（2 例），全量 **640 passed**；20 次端到端压测仍为 40/40（9.4s）。
- **证据状态进入投委会（只审计、不投票）**：已完成（2026-11-17）。`InvestmentCommittee.convene` / `_calculate_decision` 增加可选 `evidence_contract`，结果只写入 `CommitteeDecision.metadata["evidence_contract"]`（`status` / `valid` / `source_count` / `verified_count` / `unverified_count` / `unverified_sources`；未传记 `not_provided`，非 Mapping 记 `invalid_payload`），完全不参与 `status`、`approval_score`、`quorum`、`veto` 的计算。`ResearchPipeline._aggregate_evidence_contract()` 把多份报告的证据契约合并成一份（`validated` / `partial` / `not_provided`），`run()` 与 `run_with_adapters()` 均传给 `convene()`。新增 `TestCommitteeEvidenceAudit` 3 例 + 汇总函数 2 例，全量 **645 passed**，evolution 61 passed，压测 40/40（9.6s）。详见 `docs/v310_committee_audit.md` 第 6 节。


