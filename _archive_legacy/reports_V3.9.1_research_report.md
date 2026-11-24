# AI Hedge Fund OS V3.9.1 Research Report

- Generated: 2026-09-15T11:18:10

## Champion Alpha

```json
{
  "expression": "AlphaExpressionV391(operator='', children=[], feature='volatility', constant=None)",
  "signal": "0        0.224701\n1        0.115243\n2        0.238533\n3        0.294196\n4        0.115404\n           ...   \n43435    0.267145\n43436    0.140417\n43437    0.172929\n43438    0.376908\n43439    0.128982\nName: volatility, Length: 43440, dtype: float64",
  "ic_series": "date\n2022-01-03   -0.053000\n2022-01-04    0.055251\n2022-01-05    0.106634\n2022-01-06    0.109259\n2022-01-07   -0.187014\n                ...   \n2024-01-24   -0.122855\n2024-01-25    0.106939\n2024-01-26    0.009517\n2024-01-29    0.073488\n2024-01-30    0.239475\nLength: 542, dtype: float64",
  "ic": 0.010919386620026538,
  "icir": 0.0968036642989552,
  "positive_ic_ratio": 0.5387453874538746,
  "q5_q1": 0.0006534357566195137,
  "complexity": 1,
  "complexity_penalty": 0.5,
  "oos_ic": -0.004151587941233794,
  "oos_positive_ratio": 0.45786516853932585,
  "oos_days": 356,
  "robust_score": 1.6342335661086462
}
```

## Data Audit

```json
{
  "data_quality": [],
  "lookahead_rows": 0,
  "leakage": []
}
```

## Backtest Metrics

```json
{
  "total_return": -0.3885735646367656,
  "cagr": -0.13320291725632705,
  "annual_vol": 0.07371984028672803,
  "sharpe": -1.8332831794412878,
  "sortino": -3.122998250793032,
  "max_drawdown": -0.4215395140722966,
  "calmar": -0.3159915329633414
}
```

## Top Alpha Candidates

1. `volatility` | IC=0.010919 | OOS IC=-0.004152 | Score=1.6342
2. `momentum` | IC=0.003779 | OOS IC=0.005426 | Score=0.6242
3. `value` | IC=0.002219 | OOS IC=0.000688 | Score=-0.2139
4. `pb` | IC=0.001116 | OOS IC=-0.007457 | Score=-0.4732
5. `liquidity` | IC=-0.007739 | OOS IC=-0.001903 | Score=-2.1427
6. `quality` | IC=-0.006705 | OOS IC=-0.010670 | Score=-2.1456
7. `turnover` | IC=-0.010326 | OOS IC=0.011196 | Score=-2.3621

> 本报告仅用于量化研究、回测和模拟。
> 不构成投资建议，也不代表未来收益。