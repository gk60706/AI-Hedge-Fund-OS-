# V3.10 投委会投票规则审计（只审计，不改默认规则）

审计对象：`ai_team/investment_committee.py`
审计日期：2026-11-16
结论：三条规则都按现有测试规格保留，本轮不改默认行为；是否调整待决策。

## 1. 弃权计入批准率分母

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

现有 `tests/ai_team` 中的投委会用例是按上述语义写的（弃权计入分母、required 只从启用成员取、`required_members_met` 在禁用后为 True）。任何默认行为改动都会直接打破这些契约测试，因此本轮只做审计，不改代码、不改测试。

## 5. 待决策的三个选项

| 议题 | 选项 A（保持现状） | 选项 B（治理收紧） |
| --- | --- | --- |
| 弃权 | 计入分母，弃权=半个反对 | 分母剔除弃权，另记 `abstain_rate` 供披露 |
| required 禁用 | 禁用即免到场、降门槛 | 禁止禁用 required 席位，或禁用后仍计入 quorum 分母 |
| 票源 | 调用方自行映射 | ballot 增加 `agent_id` / `report_id`，一助手最多一票，重复来源拒绝 |

本轮建议：维持 A，但在报告层面显式披露「本次决议中有 N 席弃权、M 个 required 席位被禁用」；等真实 API 接入、票源可追溯后再评估 B。以上均未落地，等待拍板。
