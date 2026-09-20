# AI Hedge Fund OS — V3.9.2

V3.9.2 = AI Alpha Discovery Engine research layer.

## 完整链路

```text
历史A股数据
 -> Historical Universe
 -> PIT
 -> Factor Engine
 -> Alpha Search
 -> IC / ICIR / Q5-Q1
 -> Complexity / Correlation Dedup
 -> OOS
 -> Walk Forward
 -> Transaction Cost
 -> Portfolio Backtest
 -> Experiment Registry
 -> Alpha Library
```

## 运行

```bash
pip install -r requirements.txt
pytest -q tests
python main_v392.py --demo
```

## 交易时序

默认信号在 t 形成，使用 t+1 开盘执行；不允许用 t 收盘价假设同一收盘成交。

## PIT

历史研究必须满足 `available_date <= as_of_date`。没有可靠披露日期的基本面字段不得伪装成历史可得信息。

## 回测边界

当前默认 Long Only、T+1、100股整手、停牌/涨停/跌停约束及交易成本模型。成本参数仅为研究默认值，生产前必须按实际券商与最新规则校准。

## 研究纪律

LLM 可以提出 Alpha 假设，但 IC、ICIR、收益、回撤等指标必须由确定性计算引擎从数据计算，不能由 LLM 编造。

## 版本边界

V3.9.2 是研究与验证层，不是实盘下单系统。V3.9.3 再进入 Alpha Evolution、遗传编程、多目标优化、Alpha 衰减监控和模拟盘。
