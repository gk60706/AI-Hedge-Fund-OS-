# AI Hedge Fund OS — 架构文档（V0.1）

## 1. 目标

构建一个研究用途的 AI 股票研究系统：获取 A 股实时行情，由 CIO Agent 基于 OpenAI Responses API 生成结构化的股票研究报告。**不含自动实盘交易。**

## 2. 系统流程

```
用户请求（股票代码）
        │
        ▼
┌─────────────────┐
│  Market Tool    │  tools/market_tool.py
│  (AkShare)      │  ak.stock_zh_a_spot_em() → 行情快照 dict
└─────────────────┘
        │
        ▼
┌─────────────────┐
│  market_node    │  agents/workflow.py（LangGraph 节点）
│  (行情采集)      │
└─────────────────┘
        │
        ▼
┌─────────────────┐
│  cio_node       │  agents/cio_agent.py
│  (CIO Agent)    │  OpenAI Responses API 生成分析
└─────────────────┘
        │
        ▼
┌─────────────────┐
│  save_report    │  写入 reports/{code}_{timestamp}.md
│  (报告落盘)      │
└─────────────────┘
        │
        ▼
   返回 report + report_path
```

## 3. 模块职责

| 模块 | 文件 | 职责 |
| --- | --- | --- |
| backend | `backend/main.py` | FastAPI 入口（/health、/market、/research）与 CLI |
| backend | `backend/config.py` | 从 `.env` 读取配置（pydantic Settings + lru_cache） |
| tools | `tools/market_tool.py` | AkShare 行情封装、数据清洗、字段标准化 |
| agents | `agents/cio_agent.py` | CIO System Prompt + OpenAI Responses API 调用 |
| agents | `agents/workflow.py` | LangGraph StateGraph：market → cio → save_report |
| tests | `tests/` | pytest 单元/集成测试（mock 网络与外部 API） |

## 4. 关键设计决策

- **OpenAI Responses API**：使用 `client.responses.create(model, instructions, input, ...)`，与旧式 `chat.completions` 不同。
- **LangGraph**：`StateGraph(ResearchState)`，节点间通过共享状态传递 `market_data` / `report` / `report_path`。
- **密钥安全**：所有 Key 仅存在于本地 `.env`，`get_settings()` 从环境变量读取；`.gitignore` 强制排除 `.env`。
- **数据真实性**：CIO Prompt 明确禁止虚构财务数据、新闻、估值、机构持仓与公司公告；数据不足时输出“需要进一步研究”。

## 5. 风险与边界

- 本系统为研究辅助工具，**不是个性化投资建议**。
- V0.1 只读取公开行情数据，不发起任何交易指令。
- 真实网络环境下 AkShare 与 OpenAI API 的可达性取决于本机网络；测试全部通过 mock 保证离线可运行。

## 6. 路线图（后续版本）

- **V0.2**：Research / Quant / Risk / CIO 多 Agent + 股票评分 + AI 精选股票池。
- **V0.3**：评分 → 选股 → 回测 → 模拟交易。
- **之后**：模拟盘 → 严格风控 → QMT / 券商接口（实盘仍需另行评审）。
