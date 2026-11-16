# V3.10 多 AI 协作引擎（Multi-AI Collaboration Engine）

> 研究治理链路：三个 AI 助手各写独立报告 → 交叉校验 → 互相辩论 → 收敛共识 → 投资委员会投票。
> **不含任何自动实盘交易接口**，不产生下单指令、不做仓位建议。

## 1. 链路总览

```
TeamConfig ──► TaskManager ──► ReportCollector ──► CrossValidator
                                                   │
                                                   ▼
                                            DebateEngine
                                                   │
                                                   ▼
                                          ConsensusEngine
                                                   │
                                                   ▼
                                        InvestmentCommittee
                                                   │
                                                   ▼
                                              decision.json
```

端到端装配在 `ai_team/research_pipeline.py`（`V310ResearchPipeline`），
各阶段也可以单独调用，便于替换某一层实现。

## 2. 角色与分工

| agent_id | 角色 | 负责范围 | 委员会角色映射 |
|---|---|---|---|
| `chatgpt` | CIO（首席投资官） | 生意质量、护城河、增长可持续性、估值纪律、下行情景 | `cio`（1.5，required）+ `quant`（1.0） |
| `grok` | 市场情报 | 产业链订单、库存、价格、超大规模厂商 capex、监管与舆情 | `industry`（1.0）+ `compliance`（1.0，required） |
| `hark` | 基本面分析师 | 毛利与现金流、存货/应收质量、客户集中度、资本开支、同业估值 | `risk`（1.5，required）+ `fundamental`（1.0） |

说明：票源映射是「一位助手 → 两个委员席位」，合计权重 7。全票时法定人数自然满足；
这是研究治理的记账方式，不代表真实 6 人投委会。

## 3. 报告契约

`ai_team/report_collector.py` 的 `DEFAULT_REQUIRED_SECTIONS` 规定每份报告必须包含 7 个小节：

1. Executive Summary
2. Key Findings
3. Evidence and Sources
4. Analytical Reasoning
5. Risks and Limitations
6. Independent Conclusion
7. Confidence Level

`# Confidence Level` 必须落在 0.00–1.00。`allow_incomplete=False` 时缺任一节都会被拒收。
同一 `agent_id` 对同一 `task_id` 重复提交会抛 `DuplicateReportError`。

## 4. 辩论契约

- 立场 `DebatePosition`：`support` / `oppose` / `neutral` / `clarify`
- 结论 `DebateConclusion`：`consensus` / `partial_consensus` / `no_consensus` / `insufficient_evidence`
- 交叉校验不要求辩论时，`start_debate` 会抛 `DebateNotRequiredError`；流水线默认 `force=True`

`debate.json` 结构：

```json
{
  "contributions": [
    {"agent_id": "chatgpt", "position": "clarify", "content": "...", "evidence": ["..."]}
  ],
  "conclusion": "partial_consensus",
  "conclusion_text": "...",
  "unresolved_issues": ["..."],
  "rationale": "..."
}
```

## 5. 共识与置信度

共识状态只有四种，落库前会经过 `_KNOWN_CONSENSUS_STATUSES` 白名单校验，
未知状态直接在投委会入口抛 `CommitteeConsensusError`，不会被当成「完全共识」放行。

文字置信度 → 数值映射（`_CONFIDENCE_LEVEL_SCORES`）：

| 等级 | 数值 | 设计理由 |
|---|---|---|
| high | 0.80 | 与共识引擎 high 判定带对齐 |
| medium | 0.65 | 高于 `minimum_confidence=0.5`，留 0.15 余量，避免边界抖动 |
| low | 0.30 | 明显低于门槛，落 INSUFFICIENT_EVIDENCE |

`_normalize_confidence` 带 `math.isfinite` 防护：NaN / inf 一律按 `-1.0` 处理，
最终在 `_validate_consensus` 阶段抛错，而不是静默通过。

## 6. 投委会判定链

默认 6 委员与权重：

| member_id | 权重 | 是否 required |
|---|---|---|
| `cio` | 1.5 | 是 |
| `risk` | 1.5 | 是 |
| `quant` | 1.0 | 否 |
| `fundamental` | 1.0 | 否 |
| `industry` | 1.0 | 否 |
| `compliance` | 1.0 | 是 |

阈值：`minimum_confidence=0.5`、`approval_threshold=0.60`、`quorum=0.6`；
否决角色为 `{risk, compliance}`。

判定顺序（依次短路，先命中先定案）：

1. 法定人数或 required 委员缺席 → `deferred`
2. 共识层为 `no_consensus` / `insufficient_evidence` → `insufficient_evidence`
3. 风险/合规 reject 且开启否决 → `rejected`
4. 共识置信度低于 `minimum_confidence` → `insufficient_evidence`
5. 没有任何票 → `deferred`
6. 批准率低于 `approval_threshold` → `rejected`
7. 存在 `approve_with_conditions`、附条件、风险标记或 `partial_consensus` → `approved_with_conditions`
8. 其余 → `approved`

审计字段：`metadata.veto_triggered` 记录「是否出现否决票」，
`metadata.veto_decisive` 记录「该否决是否真正决定结果」（`veto_triggered and status == rejected`），
避免出现「法定人数不足但否决被算作决定性」的自相矛盾。

## 7. 容错与降级

`V310ResearchPipeline.submit_reports()` 支持：

| 能力 | 实现 | 行为 |
|---|---|---|
| 重试 | `RetryPolicy.attempts`（默认 2） | 单个助手提交失败后重试，不中断其他助手 |
| 超时 | `RetryPolicy.timeout_seconds`（默认不限） | 超时抛 `AgentTimeoutError` 并计数 |
| 超时实现 | `RetryPolicy.timeout_mode`：`thread`（默认）/ `process` | `thread` 只放弃等待，被卡线程仍可能跑完；`process` 用 spawn 子进程执行，超时后 `terminate → join(1s) → kill → join` 真正终止。不可 pickle 的 callable 或子进程启动失败抛 `HardTimeoutNotSupportedError`，不会静默退回线程 |
| 缺员降级 | `allow_missing` / `--allow-missing-agents` | 成功报告数低于 `min_reports`(默认 2) 时，默认抛 `InsufficientAgentsError`；显式开启才继续，并把缺口写入 `decision.json` 的 `failed_agents` |

`process` 模式的序列化约束：

- 只有模块级函数、或可 pickle 的实例（如 `_ReportCollectorCall`）才能跨进程；lambda / 闭包会被 `pickle.dumps` 预检拦下。
- 返回值必须先 `pickle.dumps` 预检，不能回传的对象按 `HardTimeoutNotSupportedError` 处理。
- `spawn` 会重新导入主模块，调用方脚本必须写 `if __name__ == "__main__":`，否则子进程启动失败。pytest 与包内 CLI 不受影响。
- 每次提交都是一次进程创建，成本明显高于线程：适合「必须能强杀」的场景，不适合高频短调用。

## 8. 命令行

```powershell
python -m ai_team.research_pipeline `
  --symbol 300394 `
  --reports-dir research\300394_2026-11-16\reports `
  --debate research\300394_2026-11-16\debate.json `
  --ballots research\300394_2026-11-16\ballots.json `
  --output research\300394_2026-11-16\decision.json `
  --project-root research\300394_2026-11-16 `
  --retry-attempts 2 `
  --timeout-seconds 90 `
  --timeout-mode process `
  --allow-missing-agents
```

参数说明：

- `--project-root` 决定 `tasks/`、`reports/`、`evaluation/` 落盘位置；指向研究目录可避免污染仓库
- `--retry-attempts` 默认 2；`--timeout-seconds` 默认不限制；`--timeout-mode` 默认 `thread`，需要硬终止时传 `process`；`--allow-missing-agents` 默认关闭
- 退出码非 0 表示阶段失败（缺员、校验不通过、共识违约等）

`decision.json` 顶层字段：`symbol`、`task_id`、`validation`、`debate`、`consensus`、`decision`、`failed_agents`。

## 9. 真实 API 模式（适配器）

`ai_team/adapters.py` 把「人工抄报告」换成可编程调用：只用标准库 HTTP，不新增第三方依赖。

| 助手 | 协议 | 必需环境变量 | 默认 |
|---|---|---|---|
| ChatGPT | OpenAI `/chat/completions` | `OPENAI_API_KEY`、`OPENAI_MODEL` | base `https://api.openai.com/v1`、model `gpt-5.5` |
| Grok | 同上（xAI 兼容） | `XAI_API_KEY`、`XAI_MODEL` | base `https://api.x.ai/v1`；**model 必须显式配置**，不预置猜测值 |
| Hark | 同上（自建网关） | `HARK_API_KEY`、`HARK_BASE_URL`、`HARK_MODEL` | 全部必填；无公开文档 API，缺配置时该席位转为人工模式 |

行为约定：

- 缺任一配置**不发请求**，登记进 `skipped` 并说明缺哪个变量；不会静默降级
- 密钥只用于 `Authorization` 头，不出现在日志、异常消息、`describe()` 或产物里
- 每次生成记录审计：`model`、`base_url`、耗时、prompt/响应字符数、`content_sha256`、`finish_reason`
- 报告正文强制 7 个英文小节（`REPORT_CONTRACT` 追加在角色提示词后），否则收集阶段整份拒收

运行：

```powershell
python main_v310.py --live `
  --symbol 300394.SZ `
  --reports-dir research\300394_live\reports `
  --project-root research\300394_live `
  --as-of 2026-11-16
```

只给 `--live`、不给 `--debate` 时，流水线跑到「报告收集 + 交叉校验」就停，输出 `stage=reports_collected`，
并写出 `generation.json`（谁被调用、用了哪个模型、内容哈希、缺少哪些助手）。辩论与投票仍需 `--debate` / `--ballots` 材料，
不会伪造。

## 10. 测试

```powershell
pytest tests\ai_team -q
```

覆盖：配置与角色、任务状态机、报告小节校验与重复提交、交叉校验、
辩论立场与结论、共识四态与置信度分级、投委会判定链与否决语义、端到端集成、
流水线重试 / 超时 / 缺员降级。

## 11. 已知限制（按现有测试规格保留）

1. **弃权计入批准率分母**：`approval_score` 的分母包含弃权票，弃权会拉低批准率。
2. **required 委员被 disable 后不再计入法定人数**，且 `required_members_met=True`。
3. **默认线程超时仍无法强杀**：`timeout_mode="thread"` 下 `ThreadPoolExecutor` 只能放弃等待，后台线程仍可能跑完；需要硬终止时显式切 `timeout_mode="process"`（受 pickle 约束，见第 7 节）。
4. **并发锁只覆盖任务与报告**：`TaskManager` 的任务文件与 `ReportCollector` 的（task_id, agent_id）报告提交已用 `FileLock` 串行化；流水线级产物（异议/共识/决议 JSON、`generation.json`）仍是后写覆盖，需要外部串行化。
5. **票源映射是一人两席**：三位助手映射到六个委员席位，属研究治理记账，不是真实 6 人投委会。
6. **证据契约只校验元数据**：`sources` 提供时会检查名称、原始链接、发布日期、数据期间、来源类型与核实状态，但 `verified` 只是提交方声明，系统不抓取链接、不比对内容；流水线目前也不传结构化来源，元数据记为 `sources_not_provided`。
