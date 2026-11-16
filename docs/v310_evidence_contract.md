# V3.10 报告证据可追溯性契约

## 1. 问题

V3.10 的三份 AI 报告只要求正文里「注明报告期和来源」，系统没有任何结构化来源校验：

- `ai_team/schemas/agent_report.schema.json` 的 `sources` 只有 `name` / `url` / `published_at` / `description`，没有数据期间、来源类型、核实状态；
- 四个提示词只有零散文字要求，没有统一的输出字段；
- `ReportCollector.validate_report()` 只看小节标题和字数；
- `CrossValidator` 从正文抓证据小节文本打分，不看结构化来源。

结果是「报告写了来源」和「来源真的可追溯」之间没有代码约束。

## 2. Schema 扩展

在 `sources.items.properties` 增加四个**可选**字段（`required` 仍只有 `name`，`additionalProperties=false` 保持不变）：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `data_period` | string | 1–100 字符，数据实际覆盖期间，如 `2026-Q2` |
| `source_type` | string | 枚举：`official` / `company_filing` / `government` / `exchange` / `academic` / `financial_data` / `news_media` / `industry_research` / `other` |
| `verification_status` | string | 枚举：`verified` / `unverified` |
| `verification_note` | string | ≤1000 字符，未核实时说明原因 |

保持可选是为了兼容历史报告与既有测试；新报告的严格性由运行时校验函数承担，而不是靠改 `required` 强制迁移。

## 3. 提示词

`ai_team/prompts/cio_chatgpt.txt`、`intelligence_grok.txt`、`analyst_hark.txt`、`general_team.txt` 末尾追加同一段《结构化证据与可追溯性要求（必须遵守）》，要求：

- 除正文说明外必须输出 `sources` 数组，字段为 `name` / `url` / `published_at` / `description` / `data_period` / `source_type` / `verification_status` / `verification_note`；
- `url` 必须是 HTTP/HTTPS 原始链接，不得用搜索结果页或二手转载页顶替；
- `published_at` 用带时区的 ISO 8601；`data_period` 与发布日期不能互相替代；
- `unverified` 是合法状态，但必须显式标注，且不得把未核实内容表述为已确认事实；
- 正文必须区分已核实事实 / 分析推断 / 待核实信息，且结构化来源与正文引用一致。

## 4. 校验函数

新增 `ai_team/evidence_contract.py`（纯函数、无第三方依赖）：

```
validate_evidence_contract(sources) -> {
    valid, source_count, verified_count, unverified_count,
    errors: [{source_index, field, code, message}],
    unverified_sources: [int, ...],
}
```

规则：

| 检查 | 失败 code |
| --- | --- |
| 空数组 / 非列表 | `missing_sources` |
| 来源不是对象 | `invalid_source` |
| `name` 缺失或空白 | `missing_name` |
| `url` 缺失 | `missing_url` |
| `url` 非 http/https 或含空白 | `invalid_url` |
| `published_at` 缺失 | `missing_published_at` |
| `published_at` 非带时区 ISO 8601 | `invalid_published_at` |
| `data_period` 缺失或空白 | `missing_data_period` |
| `source_type` 非法 | `invalid_source_type` |
| `verification_status` 缺失或非法 | `missing_or_invalid_verification_status` |

`unverified` 本身不导致失败，只会计入 `unverified_count` 并列入 `unverified_sources`。

## 5. 接入 ReportCollector

`collect_report` / `_collect_report_unlocked` 末尾增加 `sources: list[dict] | None = None`：

- `sources` 不为 `None`：调用 `validate_evidence_contract`，失败抛 `InvalidReportError`（错误信息按 `source[i].field` 拼接）；成功把结果写入元数据 `validation["evidence_contract"]`，`status="validated"`；
- `sources` 为 `None`：不校验，元数据写 `{"valid": None, "status": "sources_not_provided"}`，保留旧调用路径与 626 项回归。

校验位置在 `validate_report` 与 `strict_validation` / `allow_incomplete` 判定之后、生成 `report_id` 与写盘之前，因此证据不合格不会留下 Markdown 或元数据半成品。

与 ChatGPT 原始方案（无 `sources` 即拒绝）的差异：现有仓库有约 40 处 `collect_report` 调用（测试与 `research_pipeline._ReportCollectorCall`）都不传 `sources`，硬性必填会让全部旧链路立即失败。当前落地为「传了就严格查，没传就显式记账」，并在元数据里留下 `sources_not_provided` 供后续审计；等适配器/流水线开始产出结构化来源后，可把该状态升级为拒绝。

## 6. 测试

`tests/ai_team/test_evidence_contract.py` 6 例：

1. 完整 `verified` 来源通过，counts 正确；
2. 缺 `url` → `missing_url`；
3. 缺 `data_period` → `missing_data_period`；
4. `unverified` 显式标记可通过，`unverified_sources=[0]`；
5. 缺 `verification_status` → `missing_or_invalid_verification_status`；
6. `sources=[]` → `missing_sources`。

另用临时脚本做过一次接线验证：完整来源 → 报告落盘且 `validation["evidence_contract"]["status"] == "validated"`；删掉 `url` → `InvalidReportError: 报告证据校验失败: source[0].url: 必须提供原始来源链接。`

## 7. 明确未做

- **没有验证来源真实性**：`verified` 只是提交方的声明，系统没有抓取原始链接、比对内容或检查结论—来源对应关系；
- **流水线尚未传结构化来源**：`research_pipeline._ReportCollectorCall` 仍只传正文，适配器也还没有解析 `sources`；因此线上链路目前写入的是 `sources_not_provided`；
- **`unverified` 不影响投票**：投委会与共识引擎没有读取 `validation["evidence_contract"]`，未核实报告仍按普通报告计分。
