# AI Hedge Fund OS V1.7

AI 股票研究与量化基础设施（研究 / 模拟用途）。

当前版本只允许：**行情获取 → AI 研究 → 研究报告 / AI 选股研究 / AI 策略研究**。**不包含任何自动实盘交易接口。**

## 版本能力

- **V0.1**：行情获取（多源容灾）+ CIO 研究报告
- **V0.2**：LangGraph 多 Agent（Research / Quant / Risk / Decision）+ 综合评分 + 仓位建议
- **V0.3**：主力资金雷达 + A 股全市场扫描（五档盘口 / 资金评分 / 机会排序）
- **V0.4**：AI 基本面研究中心（财报 / 新闻 / 行业 / 护城河 / 巴菲特估值）+ AI 投资报告
- **V0.5**：AI 量化回测引擎 + Alpha 因子系统——动量 / 价值 / 主力资金因子、因子融合引擎、Backtrader 回测、最大回撤 / 夏普指标、AI 策略评价（KEEP/DROP）、Optuna 参数优化接口
- **V0.6**：AI 多策略交易引擎（模拟）——多策略资金池（动量 / 价值 / 资金）、多因子融合 Alpha、Markowitz 组合优化、风险模型（HIGH/NORMAL）、风险预算分配、动态调仓（BUY/SELL）、AI 基金经理 Agent、多策略组合入口
- **V0.7**：模拟盘交易系统（Paper Trading Engine）——虚拟资金账户、订单系统、持仓管理、模拟券商（PaperBroker）、SQLite 交易记录、交易执行引擎、AI 交易 Agent、盈亏统计、组合快照、`POST /api/v1/trade` 模拟交易 API（QMT 接口预留，不接实盘）
- **V0.8**：实时交易系统（盘中模拟）——WebSocket 实时行情客户端、Tick 引擎、分钟 K 线生成、实时资金流监控、涨停检测、自动止盈止损（20%/8%）、T+0 模拟策略、盘中 AI 决策 Agent（BUY/HOLD/SELL）、实时风险预警、实时交易循环
- **V0.9**：AI 交易大脑（LLM Trader Brain）——LangGraph Agent 框架、GPT 交易决策 Agent、市场环境 Agent、新闻分析 Agent、Quant Agent、AI CIO 基金经理、AI 长期记忆（ChromaDB）、AI 每日复盘、AI 交易日志、MCP 工具接口预留（OpenAI Responses API）
- **V1.0**：AI 自主投资基金系统 MVP——研究委员会（基本面 / 量化 / 新闻）→ CIO 决策 → 风险委员会 → 组合管理 → 晨报 / 复盘
- **V1.1**：自主投资 Agent 升级版——LangGraph 正式多 Agent 图 + MCP 工具系统 + RAG 投资知识库 + PDF 财报读取 + AI 策略生成 / 评价 / 进化（策略淘汰）
- **V1.2**：Self-Evolving AI Hedge Fund Agent（自动进化型量化研究实验室）——AI 自动发现 Alpha 因子（AlphaAgent）、AI 策略生成（StrategyAgent）、AI 代码生成（CodeAgent，OpenAI Responses API）、AI 自动回测（BacktestEngine 逐行引擎 + 回测评价 evaluate）、AI 参数优化（optimizer 网格搜索）、策略基因数据库（SQLite）、策略进化引擎（淘汰 + 变异）、总进化流程 `run_evolution.py`（研究用途，无实盘交易）
- **V1.3**：策略竞技场 + 多 Agent 基金委员会——多投资风格 Agent（价值 / 趋势 / 量化 / 宏观）、策略竞技场（StrategyArena）、策略排名（StrategyRanking）、AI 投票委员会（VotingSystem）、CIO 投资委员会（InvestmentCommittee）、风险委员会（RiskAgent）、资金自动分配（CapitalAllocator）、策略冠军上线（ChampionStrategy）、冠军历史库（ChampionDB）、`main_v13.py` 完整运行入口（研究/模拟，无实盘交易）
- **V1.4**：自动交易生产系统（Production MVP）——AkShare 行情接口（data/akshare_client.py）、行情服务（data/market_service.py）、MySQL 数据仓库（database/，连接信息全部 .env 读取）、5000 股票扫描器（scanner/stock_scanner.py + ranking.py）、模拟交易券商（trading/，V0.7 execute 与 V1.4 buy/sell 双接口并存）、持仓管理（PositionManager）、自动调仓（RebalanceEngine）、定时任务（scheduler/ APScheduler 8:30 扫描 / 15:30 复盘）、AI 每日投资日报（reports/daily_report.py）、邮件推送（notification/，未配置 SMTP 时模拟）、Docker 部署（docker/Dockerfile）、`main_v14.py` 主入口（模拟交易，无实盘接口）
- **V1.5**：实时盘中交易平台（Intraday Trading System）——WebSocket 实时行情（realtime/websocket.py）、Tick 实时数据流（tick_stream.py）、Level-5 五档盘口分析（orderbook.py，买卖压力强度）、主力资金雷达（capital/main_force.py，大单>50万评分）、分钟动量因子（intraday/momentum.py）、T+0 策略（intraday/t0_strategy.py，低吸/止盈）、AI 盘中交易 Agent（intraday/trader_agent.py，多信号加权决策）、涨停板策略（market/limit_strategy.py，≥9.8% 涨停检测）、龙虎榜 Agent（market/dragon_tiger.py，机构抢筹识别）、实时风控中心（risk/realtime_risk.py，亏损<-8% 卖出告警）、`main_v15.py` 实时交易循环（模拟决策，无实盘接口）
- **V1.6**：机器学习交易引擎（Machine Learning Trading Engine）——数据特征工程（ml/feature_engineering.py：收益率/MA5/MA20/波动率/量比/次日涨跌标签）、XGBoost 涨跌预测（ml/xgboost_model.py，XGBClassifier）、LSTM 时间序列价格预测（ml/lstm_model.py，PyTorch）、Transformer 行情模型（ml/transformer_model.py，PyTorch 编码器）、数据集加载（dataset/loader.py，80/20 划分）、模型训练评价（ml/trainer.py）、AI 模型仓库自动选择最优（models/registry.py）、多模型融合预测（prediction/ensemble.py，XGBoost 50% + LSTM 30% + Transformer 20% → BUY/SELL/HOLD）、AI 交易信号 Agent（intraday/ml_trader.py，开仓/平仓/等待）、`main_v16.py` 运行入口（模拟预测，无实盘接口）
- **V1.7**：强化学习交易 Agent（Reinforcement Learning Trading Agent）——交易状态定义（rl/state.py MarketState 状态向量）、动作空间（rl/action.py SELL/HOLD/BUY）、强化学习交易环境（rl/environment.py 简化全仓模拟）、奖励引擎（rl/reward.py 收益−回撤惩罚−过度交易惩罚）、DQN 网络与 Agent（rl/dqn_agent.py，epsilon-greedy）、PPO Actor-Critic 框架（rl/ppo_agent.py）、RL 训练器（rl/trainer.py）、风险闸门（risk/risk_gate.py，日亏-3%/回撤10% 拒绝放行）、仓位管理（risk/position_sizer.py 置信度×20%）、RL 模型评价（evaluation/rl_evaluator.py 总收益/最大回撤/Sharpe）、`main_v17.py` 模拟训练入口（研究/模拟，无实盘接口）

## 技术栈

- Python 3.11+
- FastAPI（Web API）
- LangGraph（Agent 工作流）
- OpenAI Responses API（`client.responses.create`）
- AkShare（A 股实时行情 / 财务数据）
- Backtrader（历史回测，V0.5）+ Optuna（策略参数优化，V0.5）+ scikit-learn / scipy / matplotlib
- ChromaDB（投资知识向量库，V1.1；Python 3.14 无预编译 wheel，建议 3.11-3.13 安装）

## 项目结构

```
AI-Hedge-Fund-OS/
├── agents/
│   ├── __init__.py
│   ├── models.py            # AgentResult / InvestmentDecision 统一输出模型
│   ├── common.py            # OpenAI Responses API 统一调用
│   ├── cio_agent.py         # CIO Agent：基于行情快照生成研究分析（V0.1）
│   ├── research_agent.py    # Research Agent：基本面研究（V0.2）
│   ├── quant_agent.py       # Quant Agent：技术分析（V0.2）+ V1.0 Alpha 因子版 + V1.3 QuantAgent
│   ├── risk_agent.py        # Risk Agent：风险控制（V0.2）
│   ├── decision_agent.py    # Decision Agent：多 Agent 综合决策（V0.2）
│   ├── fund_agent.py        # 主力资金 Agent（V0.3）
│   ├── opportunity_agent.py # 机会发现 Agent（V0.3）
│   ├── fundamental_agent.py # 基本面 Agent（V1.0，委员会版）
│   ├── news_agent.py        # 新闻 Agent（V1.0，委员会版）
│   ├── portfolio_agent.py   # AI 基金经理 Agent（V0.6）
│   ├── base_manager.py      # 投资经理基础类（V1.3）
│   ├── value_agent.py       # 价值投资 Agent（V1.3）
│   ├── trend_agent.py       # 趋势交易 Agent（V1.3）
│   ├── macro_agent.py       # 宏观 Agent（V1.3）
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
├── data/                          # 行情数据（V0.4 + V1.4）
│   ├── __init__.py
│   ├── financial_api.py           # 财务数据接口（V0.4）
│   ├── akshare_client.py          # V1.4 AkShare 行情接口
│   └── market_service.py          # V1.4 行情服务（最新快照）
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
├── factors/                      # V0.5 Alpha 因子系统
│   ├── __init__.py
│   ├── momentum.py               # 20 日动量因子
│   ├── value.py                  # PE 估值因子
│   ├── capital.py                # 主力资金因子
│   └── factor_engine.py          # 因子融合引擎（Alpha 评分 + 股票排序）
├── backtest/                     # V0.5 回测引擎
│   ├── __init__.py
│   ├── strategy.py               # AlphaStrategy（买入 + 回撤止损）
│   ├── engine.py                 # Backtrader 封装回测入口
│   └── metrics.py                # 最大回撤 / 夏普比率
├── ai/                           # V0.5 AI 策略研究
│   ├── __init__.py
│   ├── strategy_agent.py         # AI 策略评价 Agent（KEEP/DROP）
│   └── optimizer.py              # Optuna 自动参数搜索
├── strategies/                   # V0.6 多策略资金池
│   ├── __init__.py
│   ├── momentum_strategy.py      # 动量策略评分
│   ├── value_strategy.py         # 价值策略评分
│   ├── capital_strategy.py       # 主力资金策略评分
│   └── multi_factor.py           # 多因子融合（40/30/30）
├── trading/                      # V0.7 模拟盘交易系统 + V1.4 扩展
│   ├── __init__.py
│   ├── account.py                # 虚拟资金账户
│   ├── order.py                  # 订单系统
│   ├── position.py               # 持仓管理（Position + V1.4 PositionManager）
│   ├── broker.py                 # 模拟券商（PaperBroker，execute/buy/sell 双接口）
│   ├── execution.py              # 交易执行引擎
│   ├── performance.py            # 盈亏统计
│   ├── portfolio.py              # 组合快照
│   └── rebalance.py              # V1.4 自动调仓系统
├── database/                     # V0.7 交易记录数据库 + V1.4 MySQL
│   ├── __init__.py
│   ├── trade_db.py               # SQLite 模拟成交记录
│   ├── mysql.py                  # V1.4 MySQL 连接（.env 读取）
│   └── models.py                 # V1.4 SQLAlchemy ORM 模型
├── scanner/                      # V1.4 股票扫描器
│   ├── __init__.py
│   ├── stock_scanner.py          # AI 团队批量扫描打分
│   └── ranking.py                # AI 精选股票池
├── scheduler/                    # V1.4 定时任务
│   ├── __init__.py
│   └── jobs.py                   # APScheduler 每日扫描/复盘
├── notification/                 # V1.4 通知推送
│   ├── __init__.py
│   └── email.py                  # 邮件推送（SMTP 未配置时模拟）
├── docker/                       # V1.4 部署
│   └── Dockerfile                # python:3.11 镜像
├── realtime/                     # V0.8 实时行情 + V1.5 WebSocket 盘中行情
│   ├── __init__.py
│   ├── websocket_client.py       # WebSocket 行情客户端（模拟源）
│   ├── tick_engine.py            # Tick 数据引擎
│   ├── kline_engine.py           # 分钟 K 线生成
│   ├── capital_monitor.py        # 实时资金流 Agent
│   ├── monitor.py                # 实时交易循环（模拟）
│   ├── websocket.py              # V1.5 WebSocket 行情订阅分发
│   ├── tick_stream.py            # V1.5 Tick 实时数据流缓存
│   └── orderbook.py              # V1.5 Level-5 五档盘口分析
├── capital/                      # V1.5 主力资金雷达
│   ├── __init__.py
│   └── main_force.py             # 大单（>50万）买卖力度评分
├── intraday/                     # V0.8 盘中交易 Agent + V1.5 盘中策略
│   ├── __init__.py
│   ├── momentum_agent.py         # 涨停检测
│   ├── stop_agent.py             # 自动止盈止损（20%/8%）
│   ├── t0_agent.py               # T+0 模拟策略
│   ├── decision_agent.py         # 盘中 AI 决策（BUY/HOLD/SELL）
│   ├── momentum.py               # V1.5 分钟动量因子
│   ├── t0_strategy.py            # V1.5 T+0 策略（低吸/止盈）
│   └── trader_agent.py           # V1.5 AI 盘中交易 Agent
├── market/                       # V1.5 市场策略
│   ├── __init__.py
│   ├── limit_strategy.py         # 涨停板策略（≥9.8%）
│   └── dragon_tiger.py           # 龙虎榜 Agent（机构抢筹）
├── risk/                         # V0.8 风险预警 + V1.5 实时风控
│   ├── __init__.py
│   ├── alert.py                  # 实时风险预警（跌破止损）
│   └── realtime_risk.py          # V1.5 实时风控中心（亏损<-8% 告警）
├── config/                       # V0.9 全局配置
│   ├── __init__.py
│   └── settings.py               # API Key 只从 .env 读取
├── brain/                        # V0.9 AI 交易大脑
│   ├── __init__.py
│   ├── llm_agent.py              # OpenAI Responses API 统一封装
│   ├── market_agent.py           # 市场环境 Agent（BULL/NORMAL）
│   ├── news_agent.py             # 新闻分析 Agent
│   ├── quant_agent.py            # Quant Agent（量化信号）
│   ├── cio_agent.py              # AI CIO 基金经理
│   ├── memory.py                 # AI 长期记忆（ChromaDB）
│   └── trader_brain.py           # AI 交易决策总入口
├── workflow/                     # V0.9 LangGraph 工作流
│   ├── __init__.py
│   └── graph.py                  # market → research → decision
├── core/                        # V1.0 Agent 基础框架
│   ├── __init__.py
│   ├── agent.py                 # BaseAgent 抽象基类
│   └── config.py                # .env 读取（OPENAI_API_KEY / OPENAI_MODEL）+ 代理自动继承
├── committee/                   # V1.0 投资委员会
│   ├── __init__.py
│   ├── research_committee.py    # AI 研究委员会：多 Agent 综合评分
│   ├── cio.py                   # CIO 基金经理：研究评分 → BUY/WATCH/PASS + 仓位
│   ├── risk_committee.py        # 风险委员会：组合波动 → RED/NORMAL
│   ├── voting.py                # AI 投票委员会（V1.3）
│   ├── investment_committee.py  # CIO 投资委员会（V1.3）
│   └── risk_agent.py            # 风险委员会 Agent（V1.3）
├── arena/                       # V1.3 策略竞技场
│   ├── __init__.py
│   ├── battle.py                # StrategyArena 多经理竞争
│   ├── ranking.py               # 策略排名系统
│   └── champion.py              # 策略冠军上线（模拟）
├── allocation/                  # V1.3 资金分配
│   ├── __init__.py
│   └── capital_allocator.py     # 按策略得分加权分配资金
├── fund/                        # V1.3 AI 基金团队
│   ├── __init__.py
│   └── team.py                  # create_team 多基金经理组合
├── agent_core/                  # V1.1 LangGraph 核心
│   ├── __init__.py
│   ├── state.py                 # FundState（TypedDict）
│   └── graph.py                 # Research → Quant → Risk → Decision 图
├── mcp/                         # MCP 工具层（V1.0 / V1.1）
│   ├── __init__.py
│   ├── market_tool.py           # 行情工具（V1.0 演示版）
│   ├── report_tool.py           # 报告工具（V1.0 演示版）
│   ├── tools.py                 # V1.1 工具系统（Market/News）
│   └── server.py                # V1.1 MCP 统一管理
├── portfolio/                   # V0.6 + V1.0 组合管理
│   ├── __init__.py
│   ├── optimizer.py              # Markowitz 组合优化（V0.6）
│   ├── risk_model.py             # 组合风险模型（V0.6）
│   ├── allocator.py              # 风险预算分配（V0.6）
│   ├── rebalance.py              # 动态调仓 BUY/SELL（V0.6）
│   ├── main_engine.py            # 多策略组合入口（V0.6）
│   └── manager.py                # AI 自动调仓（V1.0）
├── rag/                         # V1.1 RAG 投资知识库
│   ├── __init__.py
│   ├── document_loader.py       # PDF 财报读取（pypdf）
│   ├── vector_store.py          # ChromaDB 向量库
│   └── retriever.py             # AI 投资记忆检索
├── strategy_lab/                # V1.1 策略实验室
│   ├── __init__.py
│   ├── generator.py             # AI 策略自动生成（OpenAI Responses API）
│   ├── evaluator.py             # 策略评价：回测指标 → KEEP/DROP
│   └── evolution.py             # 策略进化：淘汰低分策略
├── evolution/                   # V1.2 自动进化引擎
│   ├── __init__.py
│   ├── alpha_agent.py           # Alpha 因子发现 Agent
│   ├── strategy_agent.py        # AI 策略生成 Agent
│   ├── code_agent.py            # AI 代码生成 Agent（OpenAI Responses API）
│   └── evolution_engine.py      # 策略进化引擎（淘汰 + 变异）
├── optimizer/                   # V1.2 参数优化
│   ├── __init__.py
│   └── parameter_search.py      # 网格搜索自动调参
├── genome/                      # V1.2 策略基因组
│   ├── __init__.py
│   └── strategy_db.py           # 策略基因数据库（SQLite strategy.db）
├── run_evolution.py             # V1.2 总进化流程入口
├── main_v13.py                  # V1.3 完整运行入口（团队→投委会→竞技场→冠军→资金分配）
├── main.py                      # V1.0 主程序（委员会 → CIO）
├── main_v11.py                  # V1.1 启动入口（LangGraph 图）
├── main_v13.py                  # V1.3 策略竞技场入口
├── main_v14.py                  # V1.4 生产系统入口（扫描 → 精选 → 模拟持仓）
├── main_v15.py                  # V1.5 实时盘中交易入口（盘口 + 主力资金 → AI 决策）
├── main_v16.py                  # V1.6 机器学习交易入口（多模型融合 → AI 交易信号）
├── main_v17.py                  # V1.7 强化学习训练入口（DQN 模拟训练 → 评价）
├── rl/                           # V1.7 强化学习交易 Agent
│   ├── __init__.py
│   ├── state.py                  # 交易状态向量（MarketState）
│   ├── action.py                 # 动作空间（SELL/HOLD/BUY）
│   ├── environment.py            # 强化学习交易环境（简化全仓模拟）
│   ├── reward.py                 # 奖励引擎（收益−回撤−过度交易）
│   ├── dqn_agent.py              # DQN 网络与 Agent
│   ├── ppo_agent.py              # PPO Actor-Critic 框架
│   └── trainer.py                # RL 训练器
├── evaluation/                   # V1.7 RL 模型评价
│   ├── __init__.py
│   └── rl_evaluator.py           # 总收益 / 最大回撤 / Sharpe
├── ml/                           # V1.6 机器学习交易引擎
│   ├── __init__.py
│   ├── feature_engineering.py    # 特征工程（收益率/均线/波动率/量比/标签）
│   ├── xgboost_model.py          # XGBoost 涨跌预测
│   ├── lstm_model.py             # LSTM 时间序列预测（PyTorch）
│   ├── transformer_model.py      # Transformer 行情模型（PyTorch）
│   └── trainer.py                # 模型训练与评价
├── dataset/                      # V1.6 数据集加载
│   ├── __init__.py
│   └── loader.py                 # CSV 加载与 80/20 划分
├── models/                       # V1.6 AI 模型仓库
│   ├── __init__.py
│   └── registry.py               # 模型注册与最优选择
├── prediction/                   # V1.6 多模型融合预测
│   ├── __init__.py
│   └── ensemble.py               # XGBoost 50% + LSTM 30% + Transformer 20%
├── reports/
│   ├── __init__.py
│   ├── report_generator.py      # AI 投资报告生成（V0.4）
│   ├── morning_report.py        # 每日晨报（V1.0）
│   ├── evening_report.py        # 晚间复盘（V1.0）
│   ├── daily_report.py          # V1.4 AI 每日投资日报
│   └── .gitkeep
├── tests/
│   ├── test_market_tool.py
│   ├── test_workflow.py
│   ├── test_api.py
│   ├── test_config.py
│   ├── test_agents_v02.py
│   ├── test_scanners.py
│   ├── test_fundamental.py
│   ├── test_v10.py              # V1.0 委员会流程
│   └── test_v11.py              # V1.1 LangGraph/MCP/RAG/策略实验室
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

# 7. V1.0 MVP 演示（研究委员会 → CIO 决策）
python main.py

# 8. V1.1 LangGraph 工作流演示
python main_v11.py

# 9. V1.2 自动进化流程演示（发现因子 → 生成策略 → 存活判定）
python run_evolution.py

# 10. V1.3 策略竞技场演示（AI 基金团队 → 投委会 → 冠军 → 资金分配）
python main_v13.py

# 11. V1.4 生产系统演示（AI 扫描 → 股票池 → 模拟持仓）
python main_v14.py

# 12. V1.5 实时盘中交易演示（五档盘口 + 主力资金 → AI 盘中决策）
python main_v15.py

# 13. V1.6 机器学习交易演示（多模型融合预测 → AI 交易信号）
python main_v16.py

# 14. V1.7 强化学习训练演示（DQN 模拟市场训练 → 评价）
python main_v17.py
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

- **OpenAI**：本机检测到系统代理（Clash 等）时会自动继承（`backend/config.py` 与
  `core/config.py` 均读取 WinINET 代理），无需手动设置；若无法访问 `api.openai.com`，
  请先确认代理可用，或用 `AUTO_SYSTEM_PROXY=0` 关闭自动继承并自行设置 `HTTPS_PROXY`。
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
- **V1.1 strategy_lab**：策略生成器统一使用 OpenAI Responses API，模型名与
  API Key 从 `.env` 读取（`core/config.py`）。

## 工作流

```
V0.1  CIO 研究：  AkShare → Market Tool → CIO Agent → LangGraph → 报告
V0.2  多 Agent：  AkShare → Research/Quant/Risk → Decision → BUY/HOLD/AVOID + 仓位
V0.3  资金雷达：  股票池(5000) → 五档盘口/资金评分 → 机会排序 → TOP50
V0.4  基本面：    TOP50 → 财报/新闻/行业/护城河/估值 → AI 投资报告 → 排序
V1.0  委员会：    基本面/量化/新闻 → 研究委员会 → CIO → 风险委员会 → 组合 → 晨报/复盘
V1.1  自主进化：  LangGraph 图 → MCP 工具 → RAG 记忆 → 策略生成/回测评价/淘汰
V1.2  自动进化：  发现因子 → 生成策略 → 代码生成 → 自动回测 → 参数优化 → 淘汰/变异 → 基因库
V1.3  竞技场：    AI 基金团队 → 竞技场竞争 → 排名 → 投委会投票 → 冠军上线 → 资金自动分配
V1.4  生产系统：  AkShare 行情 → 股票扫描 → AI 分析 → 股票池 → 模拟交易 → 组合管理 → 日报推送 → AI 复盘
V1.5  盘中交易：  WebSocket 行情 → 五档盘口 → 主力资金 → 分钟因子 → AI 盘中决策 → T+0/涨停/龙虎榜 → 实时风控
V1.6  机器学习：  特征工程 → XGBoost/LSTM/Transformer → 模型融合 → AI 交易信号 → 开仓/平仓/等待
V1.7  强化学习：  模拟市场 → Trading Environment → DQN/PPO Agent → 训练 → Risk Gate → 模拟盘
```

生成的 CIO 报告保存在 `reports/{code}_{timestamp}.md`。

## 安全

- 所有 API Key 只能从 `.env` 读取，`.env` 已被 `.gitignore` 排除，**绝不能提交 GitHub**。
- 仓库中只提交 `.env.example`（占位值）。
- 泄露过的 Key 应立即废弃并重新生成。

## 路线图

- V0.1-V0.4（已发布）：行情 / 多 Agent 研究 / 资金雷达 / 基本面中心
- V1.0（已发布）：AI 自主投资基金 MVP（研究委员会 + CIO + 风控 + 组合 + 晨晚报）
- V1.1（已发布）：自主投资 Agent 升级版（LangGraph 正式图 + MCP + RAG + 策略进化）
- V1.2（已发布）：Self-Evolving AI Hedge Fund Agent（自动进化基金：因子发现 / 策略生成 / 代码生成 / 自动回测 / 参数优化 / 策略基因库 / 进化引擎）
- V1.3（已发布）：策略竞技场 + 多 Agent 基金委员会（牛市/熊市/价值/趋势/高频 Agent、多策略资金分配、AI 投票委员会、策略冠军自动上线）
- V1.4（已发布）：自动交易生产系统（AkShare/Tushare 实时行情、MySQL 数据仓库、实时扫描、自动模拟交易、晨晚报推送、Docker 部署、Web 管理后台）
- V1.5（已发布）：实时盘中交易平台（WebSocket 实时行情、Level-5 五档盘口、主力资金流模型、分钟级 Alpha 因子、AI 盘中交易 Agent、自动 T+0 模拟、涨停板策略、龙虎榜 Agent、实时风控中心）
- V1.6（已发布）：机器学习交易引擎（XGBoost 涨跌预测、LSTM 时间序列、Transformer 行情模型、特征工程、模型融合、模型仓库自动选择、AI 交易信号）
- V1.7（当前）：强化学习交易 Agent（Deep RL、PPO/DQN、AI 模拟交易训练、自动仓位管理、风险收益优化、RL 模型评价、风险闸门）
- V1.8（规划）：AI 强化学习真实历史数据训练平台（用真实历史行情训练，替换模拟数据）

**注意**：本项目仅用于研究与模拟，不构成投资建议。禁止接入真实交易接口。
