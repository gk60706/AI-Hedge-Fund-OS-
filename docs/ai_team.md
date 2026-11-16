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
| 缺员降级 | `allow_missing` / `--allow-missing-agents` | 成功报告数低于 `min_reports`(默认 2) 时，默认抛 `InsufficientAgentsError`；显式开启才继续，并把缺口写入 `decision.json` 的 `failed_agents` |

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
  --allow-missing-agents
```

参数说明：

- `--project-root` 决定 `tasks/`、`reports/`、`evaluation/` 落盘位置；指向研究目录可避免污染仓库
- `--retry-attempts` 默认 2；`--timeout-seconds` 默认不限制；`--allow-missing-agents` 默认关闭
- 退出码非 0 表示阶段失败（缺员、校验不通过、共识违约等）

`decision.json` 顶层字段：`symbol`、`task_id`、`validation`、`debate`、`consensus`、`decision`、`failed_agents`。

## 9. 测试

```powershell
pytest tests\ai_team -q
```

覆盖：配置与角色、任务状态机、报告小节校验与重复提交、交叉校验、
辩论立场与结论、共识四态与置信度分级、投委会判定链与否决语义、端到端集成、
流水线重试 / 超时 / 缺员降级。

## 10. 已知限制（按现有测试规格保留）

1. **弃权计入批准率分母**：`approval_score` 的分母包含弃权票，弃权会拉低批准率。
2. **required 委员被 disable 后不再计入法定人数**，且 `required_members_met=True`。
3. **超时无法真正终止线程**：`ThreadPoolExecutor` 只能放弃等待，后台线程仍可能跑完；
   真实部署应把 agent 调用放到可杀死的进程或远端任务里。
4. **无跨进程并发锁**：多个流水线同时写同一 `project_root` 时不做互斥，需要外部串行化。
5. **票源映射是一人两席**：三位助手映射到六个委员席位，属研究治理记账，不是真实 6 人投委会。
