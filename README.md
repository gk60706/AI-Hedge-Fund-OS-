# AI Hedge Fund OS V0.4

AI 股票研究与量化基础设施（研究 / 模拟用途）。

当前版本只允许：**行情获取 → AI 研究 → 研究报告 / AI 选股研究**。**不包含任何自动实盘交易接口。**

## 版本能力

- **V0.1**：行情获取（多源容灾）+ CIO 研究报告
- **V0.2**：LangGraph 多 Agent（Research / Quant / Risk / Decision）+ 综合评分 + 仓位建议
- **V0.3**：主力资金雷达 + A 股全市场扫描（五档盘口 / 资金评分 / 机会排序）
- **V0.4**：AI 基本面研究中心（财报 / 新闻 / 行业 / 护城河 / 巴菲特估值）+ AI 投资报告

## 技术栈

- Python 3.11+
- FastAPI（Web API）
- LangGraph（Agent 工作流）
- OpenAI Responses API（`client.responses.create`）
- AkShare（A 股实时行情 / 财务数据）

## 项目结构

```
AI-Hedge-Fund-OS/
├── agents/
│   ├── __init__.py
│   ├── models.py            # AgentResult / InvestmentDecision 统一输出模型
│   ├── common.py            # OpenAI Responses API 统一调用
│   ├── cio_agent.py         # CIO Agent：基于行情快照生成研究分析（V0.1）
│   ├── research_agent.py    # Research Agent：基本面研究（V0.2）
│   ├── quant_agent.py       # Quant Agent：技术分析（V0.2）
│   ├── risk_agent.py        # Risk Agent：风险控制（V0.2）
│   ├── decision_agent.py    # Decision Agent：多 Agent 综合决策（V0.2）
│   ├── fund_agent.py        # 主力资金 Agent（V0.3）
│   ├── opportunity_agent.py # 机会发现 Agent（V0.3）
│   └── workflow.py          # LangGraph 工作流：CIO 流 + V0.2 多 Agent 流
├── backend/
│   ├── __init__.py
│   ├── config.py            # 配置（所有 API Key 只从 .env 读取；自动继承系统代理）
│   └── main.py              # FastAPI 入口 + CLI
├── tools/
│   ├── __init__.py
│   └── market_tool.py       # 行情封装（东财/腾讯/新浪多源容灾 + V0.2 兼容接口）
├── scanners/
│   ├── __init__.py
│   ├── stock_pool.py        # A 股股票池 + 流动性过滤（V0.3）
│   ├── order_book.py        # 新浪五档盘口（V0.3）
│   ├── capital_flow.py      # 主力资金评分模型（V0.3）
│   └── scanner.py           # 全市场扫描器（V0.3）
├── data/
│   ├── __init__.py
│   └── financial_api.py     # 财务数据接口（V0.4）
├── fundamental/
│   ├── __init__.py
│   ├── financial_agent.py   # 财报分析 Agent（V0.4）
│   ├── pdf_agent.py         # PDF 财报读取 Agent（V0.4）
│   ├── news_agent.py        # 新闻舆情 Agent（V0.4）
│   ├── industry_agent.py    # 行业景气 Agent（V0.4）
│   ├── moat_agent.py        # 企业护城河 Agent（V0.4）
│   ├── valuation_agent.py   # 巴菲特估值 Agent（V0.4）
│   └── fundamental_engine.py# 基本面综合引擎（V0.4）
├── pipeline/
│   ├── __init__.py
│   └── fundamental_pipeline.py  # V0.3 机会池 → V0.4 基本面 → AI 选股排序
├── reports/
│   ├── __init__.py
│   ├── report_generator.py  # AI 投资报告生成（V0.4）
│   └── .gitkeep
├── tests/
│   ├── test_market_tool.py
│   ├── test_workflow.py
│   ├── test_api.py
│   ├── test_config.py
│   ├── test_agents_v02.py
│   ├── test_scanners.py
│   └── test_fundamental.py
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
# 编辑 .env，填入新的 OPENAI_API_KEY（ChatGPT 对话中暴露过的 Key 视为已泄露，应废弃重生成）

# 4. 运行测试
pytest

# 5. CLI 模式：对 300394（天孚通信）生成 CIO 研究报告
python -m backend.main --code 300394

# 6. API 模式
uvicorn backend.main:app --reload
# 打开 http://127.0.0.1:8000/docs
```

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| GET | `/api/v1/market/{code}` | 获取 A 股实时行情（多源容灾） |
| GET | `/api/v1/research/{code}` | CIO 研究工作流并生成报告（V0.1） |
| GET | `/api/v1/research-agents/{code}` | 多 Agent 研究：Research/Quant/Risk → 决策（V0.2） |
| GET | `/api/v1/scan?top_n=50` | 全市场扫描：主力资金评分 → 机会 TOP50（V0.3，重负载） |
| GET | `/api/v1/ai-selection` | AI 选股流水线：机会池 → 基本面研究 → 排序（V0.4） |

## 网络说明（重要）

- **OpenAI**：本机检测到系统代理（Clash 等）时会自动继承（`backend/config.py` 读取
  WinINET 代理），无需手动设置；若无法访问 `api.openai.com`，请先确认代理可用，
  或用 `AUTO_SYSTEM_PROXY=0` 关闭自动继承并自行设置 `HTTPS_PROXY`。
- **东方财富行情**：行情接口（push2）直连更稳定，默认绕过代理；
  如需走代理，设置 `EASTMONEY_USE_PROXY=1`。
- **多源容灾**：行情获取按 **东财 push2 → 腾讯 qt.gtimg.cn → 新浪 hq.sinajs.cn**
  自动降级（输出字段一致，`source` 字段标明实际数据源）。
  东财 WAF 会对同一 IP 的突发请求临时重置连接（全市场快照最易触发），
  单股接口 + 浏览器头 + 编号子域轮换 + 指数退避重试已内置，
  且任一条源被限流时自动切换到可用源，正常单次调用即可成功。
- **V0.3 全市场扫描**会请求全市场股票池（东财快照）+ 逐只新浪盘口，
  属于重负载操作，且依赖东财/新浪当前限流状态；限流时返回空结果并提示稍后重试。
- 模型默认 `gpt-5`（`OPENAI_MODEL` 在 `.env` 中配置）。gpt-5 的 Responses API
  不支持 `temperature` 参数，程序调用时已按该模型规范处理。

## 工作流

```
V0.1  CIO 研究：  AkShare → Market Tool → CIO Agent → LangGraph → 报告
V0.2  多 Agent：  AkShare → Research/Quant/Risk → Decision → BUY/HOLD/AVOID + 仓位
V0.3  资金雷达：  股票池(5000) → 五档盘口/资金评分 → 机会排序 → TOP50
V0.4  基本面：    TOP50 → 财报/新闻/行业/护城河/估值 → AI 投资报告 → 排序
```

生成的 CIO 报告保存在 `reports/{code}_{timestamp}.md`。

## 安全

- 所有 API Key 只能从 `.env` 读取，`.env` 已被 `.gitignore` 排除，**绝不能提交 GitHub**。
- 仓库中只提交 `.env.example`（占位值）。
- 泄露过的 Key 应立即废弃并重新生成。

## 路线图

- V0.1（已发布）：行情 + AI 研究 + 研究报告
- V0.2（已发布）：Research / Quant / Risk / Decision 多 Agent + 综合评分
- V0.3（已发布）：主力资金雷达 + 全市场扫描 + 机会排序
- V0.4（当前）：AI 基本面研究中心 + AI 投资报告
- V0.5（规划）：AI 量化回测引擎 + 因子系统

**注意**：本项目仅用于研究与模拟，不构成投资建议。禁止接入真实交易接口。
