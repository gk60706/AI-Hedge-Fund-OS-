# AI Hedge Fund OS V0.1

AI 股票研究与量化基础设施 MVP（研究 / 模拟用途）。

当前版本只允许：**行情获取 → AI 研究 → 研究报告**。**不包含任何自动实盘交易接口。**

## 技术栈

- Python 3.11+
- FastAPI（Web API）
- LangGraph（Agent 工作流）
- OpenAI Responses API（`client.responses.create`）
- AkShare（A 股实时行情）

## 项目结构

```
AI-Hedge-Fund-OS/
├── agents/
│   ├── __init__.py
│   ├── cio_agent.py        # CIO Agent：基于行情快照生成研究分析
│   └── workflow.py         # LangGraph 工作流：行情 → CIO → 保存报告
├── backend/
│   ├── __init__.py
│   ├── config.py           # 配置（所有 API Key 只从 .env 读取）
│   └── main.py             # FastAPI 入口 + CLI
├── tools/
│   ├── __init__.py
│   └── market_tool.py      # 行情封装（AkShare/东财 push2 单股实时接口）
├── tests/
│   └── test_market_tool.py
├── reports/                # 生成的 Markdown 研究报告（不提交）
│   └── .gitkeep
├── docs/
│   └── architecture.md
├── .env.example            # 密钥模板（占位值）
├── .gitignore              # .env 永不提交
├── requirements.txt
└── README.md
```

## 快速开始

```powershell
# 1. 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置密钥（只在本机，绝不提交）
copy .env.example .env
# 编辑 .env，填入新的 OPENAI_API_KEY

# 4. 运行测试
pytest

# 5. CLI 模式：对 300394（天孚通信）生成研究报告
python -m backend.main --code 300394

# 6. API 模式
uvicorn backend.main:app --reload
# 打开 http://127.0.0.1:8000/docs
```

## 网络说明（重要）

- **OpenAI**：本机检测到系统代理（Clash 等）时会自动继承（`backend/config.py` 读取
  WinINET 代理），无需手动设置；若无法访问 `api.openai.com`，请先确认代理可用，
  或用 `AUTO_SYSTEM_PROXY=0` 关闭自动继承并自行设置 `HTTPS_PROXY`。
- **东方财富行情**：行情接口（push2）直连更稳定，默认绕过代理；
  如需走代理，设置 `EASTMONEY_USE_PROXY=1`。
- 东方财富 WAF 会对同一 IP 的突发请求临时重置连接，`market_tool` 已内置
  指数退避重试（最多 5 次），正常单次调用即可成功。
- 模型默认 `gpt-5`（`OPENAI_MODEL` 在 `.env` 中配置）。gpt-5 的 Responses API
  不支持 `temperature` 参数，程序调用时已按该模型规范处理。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| GET | `/api/v1/market/{code}` | 获取 A 股实时行情（AkShare） |
| GET | `/api/v1/research/{code}` | 运行 LangGraph 研究工作流并生成报告 |

## 工作流

```
AkShare → Market Tool → CIO Agent → LangGraph → AI 股票研究报告
```

生成的报告保存在 `reports/{code}_{timestamp}.md`。

## 安全

- 所有 API Key 只能从 `.env` 读取，`.env` 已被 `.gitignore` 排除，**绝不能提交 GitHub**。
- 仓库中只提交 `.env.example`（占位值）。
- 泄露过的 Key 应立即废弃并重新生成。

## 路线图

- V0.1（当前）：行情 + AI 研究 + 研究报告
- V0.2：Research / Quant / Risk / CIO 多 Agent + 股票评分
- V0.3：选股 + 回测 + 模拟交易
- 之后：模拟盘 + 严格风控 + QMT / 券商接口

**注意**：本项目仅用于研究与模拟，不构成投资建议。
