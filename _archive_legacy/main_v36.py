"""AI Hedge Fund OS V3.6 真实 A 股历史数据研究平台。

从“模拟回测框架”进入“真实 A 股历史数据研究平台”：
真实行情、交易日、复权、涨跌停、停牌、T+1、100 股整数手、
佣金/印花税/滑点、基准指数、数据缓存。

运行：python main_v36.py
"""

from __future__ import annotations

from data.price_loader import PriceLoader
from validation.data_quality import DataQualityChecker
from market.limit_rules import LimitRule


def main():
    code = "300394"
    print("\n==============================")
    print("AI Hedge Fund OS V3.6")
    print("Real A-Share Data Engine")
    print("==============================\n")

    # -------------------------
    # Load
    # -------------------------
    loader = PriceLoader()
    df = loader.load(
        code=code,
        start_date="20200101",
        end_date="20261231",
    )
    print("股票:", code)
    print("数据量:", len(df))
    print("开始:", df["日期"].min())
    print("结束:", df["日期"].max())

    # -------------------------
    # Data Quality
    # -------------------------
    checker = DataQualityChecker()
    quality = checker.check(df)
    print("\n===== DATA QUALITY =====")
    print(quality)

    # -------------------------
    # Limit Rule
    # -------------------------
    rule = LimitRule()
    latest = df.iloc[-1]
    if len(df) >= 2:
        previous = df.iloc[-2]
        limit_up = rule.is_limit_up(previous["收盘"], latest["收盘"], code)
        limit_down = rule.is_limit_down(previous["收盘"], latest["收盘"], code)
        print("\n===== MARKET RULE =====")
        print("Limit Up:", limit_up)
        print("Limit Down:", limit_down)


if __name__ == "__main__":
    main()
