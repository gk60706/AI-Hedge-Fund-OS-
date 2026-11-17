# V3.10 投委会投票规则审计（只审计，不改默认规则）

审计对象：`ai_team/investment_committee.py`
审计日期：2026-11-16
结论：三条规则在审计时（2026-11-16）都按现有测试规格保留；2026-11-17 已完成决策与落地（见第 5 节），现行行为以第 5 节为准。

## 1. 弃权计入批准率分母

> 本节记录审计时的现状（2026-11-16）。2026-11-17 决策为「保持计入 + 强制披露」，落地见 5.1。

代码事实（`_calculate_decision`）：

- `total_weight` = 所有已提交 ballot 的委员权重之和，**包含 abstain**；
- `positive_weight` = 仅 `approve` / `approve_with_conditions` 的权重；
- `approval_score = positive_weight / total_weight`；
- 默认 `approval_threshold = 0.67`，`quorum = 0.60`。

影响示例（默认 6 席：cio 1.5、risk 1.5、quant 1.0、fundamental 1.0、industry 1.0、compliance 1.0，合计 7.0）：

| 票型 | 计入弃权（现状） | 剔除弃权（假设） |
| --- | --- | --- |
| 3 赞成（4.0）+ 2 弃权（2.0）+ 1 反对（1.0） | 4.0 / 7.0 = **0.571，否决** | 4.0 / 5.0 = 0.800，通过 |

即：弃权票在现状下等价于「反对一半」——它既不表达反对，又把批准率往下拉。对于「不愿表态」的合规/风控席位，这会让否决更容易发生。

## 2. required 委员被 disable 后不再计入法定人数，且 `required_members_met=True`

> 本节记录审计时的现状（2026-11-16）。2026-11-17 已收紧为「禁用 → 决议强制 DEFERRED」，落地见 5.2。

代码事实：

- `active_members` = `self.members` 中 `enabled=True` 的成员；
- `required_ids` 只从 `active_members` 里取 `required=True` 的成员；
- `required_members_met = required_ids.issubset(已投票成员)`；
- `quorum_met = len(ballots) / len(active_members) >= quorum`。

影响示例：把 `risk`（required，权重 1.5）设为 `enabled=False`：

- `required_ids` 变为 {cio, compliance}，风控缺席不再阻止决议，`required_members_met=True`；
- 分母从 6 降为 5，3 张票即可满足 0.60 quorum（3/5），比原来的 4 票更容易开会成功。

也就是说：禁用一名 required 委员同时**降低法定人数门槛**并**免除该席位的到场要求**，两项效果叠加。

## 3. 「一位 AI → 两个席位」的票源映射

代码事实：

- 默认委员会是 6 个不同 `member_id` / `role` 的席位（cio、risk、quant、fundamental、industry、compliance）；
- `convene()` 接受调用方传入的 `ballots`，只校验 `member_id` 属于启用委员、不重复、票型合法；
- **没有**任何字段把 ballot 绑定到具体 AI 助手或具体报告；同一来源可以提交 6 张 `member_id` 不同的票。

因此「一位 AI 两席」不是代码里写死的映射，而是调用侧的记账方式（三位助手覆盖六个席位）。代码层面无法阻止「同一助手填满六个席位」，也无法从 ballot 追溯到它由哪份报告、哪个助手生成。这是治理风险，不是数值 bug。

## 4. 与现有测试的关系

现有 `tests/ai_team` 中的投委会用例原本按上述语义写死（弃权计入分母、required 只从启用成员取、`required_members_met` 在禁用后为 True）。2026-11-17 的门槛规则收紧只改写了其中 1 个断言（`test_disabled_members_are_not_part_of_active_quorum`），其余契约测试保持不变。

## 5. 决策与落地（2026-11-17）

| 议题 | 选项 A（保持现状） | 选项 B（治理收紧） | 本次决策 |
| --- | --- | --- | --- |
| 弃权 | 计入分母，弃权=半个反对 | 分母剔除弃权，另记 `abstain_rate` 供披露 | **取 A + 强制披露** |
| required 禁用 | 禁用即免到场、降门槛 | 禁止禁用 required 席位，或禁用后仍计入 quorum 分母 | **取 B** |
| 票源 | 调用方自行映射 | ballot 增加 `agent_id` / `report_id`，一助手最多一票，重复来源拒绝 | **取 B，但仅在显式提供 `agent_id` 时生效** |

### 5.1 弃权：保持计入分母（A），补齐披露

`approval_score = positive_weight / total_weight` 语义不变，`total_weight` 仍含弃权票权重。理由是 `approval_threshold = 0.67` 表达的是「绝对多数权重背书」，把弃权剔除分母会让「3 席赞成 + 3 席弃权」变成 100% 通过，而实际只有半数席位背书。

新增披露字段（全部在 `CommitteeDecision.metadata`，不参与判定）：

- `abstain_count` / `abstain_weight` / `abstain_rate`
- `vote_breakdown`：`approve` / `approve_with_conditions` / `reject` / `abstain` 四类票数
- `source_breakdown`：`{agent_id: [member_id, ...]}`

### 5.2 required 席位被禁用：决议强制 DEFERRED

原实现先按 `enabled` 过滤成员，导致禁用一名 required 委员同时免除其到场要求、并把 quorum 分母调小。改为：

- `convene()` 保留完整声明成员 `declared_members`，`active_members` 仍只含 `enabled=True`，`participation_rate` 语义不变（分母仍是启用成员）；
- 计算 `required_disabled_members`（声明中 `required=True` 且 `enabled=False` 的成员）；
- `required_members_met = not required_disabled_members and required_ids ⊆ 已投票成员`，因此只要存在被禁用的 required 席位，状态即落到 `DEFERRED`，`force=True` 也不放行；
- metadata 新增 `required_disabled_members` 与 `required_members_declared`。

### 5.3 票源可追溯：`agent_id` / `report_id`（向后兼容）

`CommitteeBallot` 新增两个 keyword-only 字段 `agent_id` / `report_id`（默认 `None`），`__post_init__` 校验非空字符串。行为差异只在显式传值时出现：

- 传了 `agent_id`：同一 `agent_id` 不得投多票，重复抛 `CommitteeValidationError`；`source_breakdown` 记录来源；
- 全部为 `None`：与旧行为完全一致，不做任何来源校验（既有 645 项 `tests/ai_team` 用例零改动）。

`CommitteeDecision.from_dict` 对旧 JSON 缺字段时回填 `None`。

### 5.4 对既有契约的影响

唯一被改写的既有断言之初是 `TestCommitteeGovernanceBoundaries::test_disabled_members_are_not_part_of_active_quorum`：原断言「禁用 required 后 `required_members_met=True`、状态 `APPROVED`」，现改为「`required_members_met=False`、状态 `DEFERRED`」，`quorum_met=True` 保留。这是一次**有意的行为收紧**，不是回归。

新增 5 个用例（`TestCommitteeGovernanceTightening`）覆盖：弃权口径披露、`agent_id` 重复拒绝/`None` 放行、空值与非字符串校验、旧 JSON 兼容、required 禁用 + `force=True` 仍 DEFERRED。

### 5.5 仍然不做的两件事

1. **证据状态不参与投票**：`metadata["evidence_contract"]` 只记录不干预，理由见第 6 节。
2. **`sources_not_provided` 不升级为拒绝**：无 sources 的报告仍被接收，等真实 API 接入、样本足够后再评估收紧。

## 6. 证据状态接入（已落地，2026-11-17）

`InvestmentCommittee.convene` / `_calculate_decision` 增加可选关键字参数 `evidence_contract`，结果只写进 `CommitteeDecision.metadata["evidence_contract"]`：

| 情形 | 写入内容 |
| --- | --- |
| 未传 | `{"status": "not_provided"}` |
| 传 Mapping | `status` / `valid` / `source_count` / `verified_count` / `unverified_count` / `unverified_sources`（计数非数字时给 `None`） |
| 传非 Mapping | `{"status": "invalid_payload"}`，不抛异常 |

**它不参与任何计算**：`status`、`approval_score`、`participation_rate`、`quorum_met`、`required_members_met`、`veto_triggered` 的判定路径完全不读该参数。测试 `TestCommitteeEvidenceAudit` 3 例显式断言「传与不传，决议结果逐字段相同」。

流水线侧 `ResearchPipeline._aggregate_evidence_contract()` 把多份报告的 `validation["evidence_contract"]` 合并：全部合格 → `validated`，全部缺失 → `not_provided`，混合 → `partial`；同时求和 `source_count` / `verified_count` / `unverified_count`，并给出 `unverified_report_count`（含未核实来源的报告数）与 `report_count`。`run()` 与 `run_with_adapters()` 都把这份汇总传给 `convene()`。

**为什么这一版不让证据影响投票**：`verified` 只是模型自述，系统不抓取链接、不比对内容；在没有回测证据说明「低证据质量报告预测更差」之前，用证据状态改 approval 等于引入无法验证的偏差项。先积累 `metadata`，有真实样本后再评估是否加权或提门槛。
