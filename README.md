# AI Hedge Fund OS

> 版本 v0.1.0 · Python 3.11+ · FastAPI · LangGraph · OpenAI Responses API · AkShare

AI Hedge Fund OS 是一套面向 A 股的**研究型**开源系统，当前版本只提供三大能力：

| 能力 | 说明 | 技术栈 |
| --- | --- | --- |
| 行情获取 | 日线历史行情、实时快照、个股基本信息 | AkShare |
| AI 研究 | 基于行情数据的结构化研究报告生成 | LangGraph + OpenAI Responses API |
| 研究报告 | 报告落盘、列表与检索 | FastAPI + Markdown 文件 |

## 安全边界（重要）

- **禁止自动实盘交易**：本系统不包含任何下单、撤单、账户、持仓或资金接口，也不对接任何券商/交易所交易通道。
- **API Key 只从 `.env` 读取**：代码中不硬编码任何密钥；`.env` 已被 `.gitignore` 排除，**严禁提交到 GitHub**。
- 行情数据仅用于研究与展示，不构成投资建议。

## 技术栈

- Python 3.11+
- [FastAPI](https://fastapi.tiangolo.com/) —— Web 服务
- [LangGraph](https://langchain-ai.github.io/langgraph/) —— 研究流程编排（有向图）
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) —— AI 文本生成
- [AkShare](https://akshare.akfamily.xyz/) —— A 股行情数据

## 目录结构

```
AI-Hedge-Fund-OS/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── core/                # 配置（.env 读取）与日志
│   ├── market/              # 行情获取（AkShare 封装 + 响应模型）
│   ├── ai/                  # AI 研究（OpenAI 客户端 / LangGraph 图 / 节点 / 提示词）
│   ├── reports/             # 研究报告存储服务
│   └── api/routes/          # REST 路由：market / research / reports
├── tests/                   # pytest 测试（数据源与 LLM 全部 mock）
├── requirements.txt
├── pyproject.toml
├── .env.example             # 环境变量示例（复制为 .env 使用）
└── .gitignore
```

## 快速开始

### 1. 环境准备

```bash
# Python 3.11+
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 配置密钥

```bash
cp .env.example .env
# 编辑 .env，填入真实 OPENAI_API_KEY
```

> `.env` 不会、也不允许被提交到 GitHub（见 `.gitignore`）。

### 3. 启动服务

```bash
uvicorn app.main:app --reload --port 8000
```

浏览器打开 <http://127.0.0.1:8000/docs> 查看交互式 API 文档。

### 4. 运行测试

```bash
pytest
```

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| GET | `/api/v1/market/history?symbol=000001&adjust=qfq` | 日线历史行情 |
| GET | `/api/v1/market/quote?symbol=000001` | 实时快照行情 |
| POST | `/api/v1/research/analyze` | 运行研究流程并生成报告 |
| GET | `/api/v1/reports` | 报告列表 |
| GET | `/api/v1/reports/{report_id}` | 报告内容 |

### 示例：生成研究报告

```bash
curl -X POST http://127.0.0.1:8000/api/v1/research/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol": "000001", "focus": "综合"}'
```

## 研究流程（LangGraph）

```
START → fetch_market_data → generate_report → END
```

1. `fetch_market_data`：通过 AkShare 获取日线历史与公司信息；
2. `generate_report`：将数据摘要组装为提示词，调用 OpenAI Responses API 生成 Markdown 报告；
3. 报告自动落盘到 `reports/` 目录，可通过 REST 接口检索。

## 开发规划（后续版本）

- 多标的研究对比、行业轮动研究
- 报告导出（PDF / 网页）
- 技术指标计算（MA / MACD / RSI）
- 研究任务异步化与任务队列

> 交易类能力（模拟盘/实盘）不在本仓库当前规划内，保持研究工具属性。

## 免责声明

本项目仅用于学习与研究，不构成任何投资建议。股市有风险，投资需谨慎。
