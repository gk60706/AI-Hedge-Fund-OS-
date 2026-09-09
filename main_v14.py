"""V1.4 主入口：AI 基金团队扫描股票池 → 精选 → 模拟持仓。

研究/模拟用途，不接入任何真实交易接口。
"""

from fund.team import create_team
from scanner.ranking import StockRanking
from scanner.stock_scanner import StockScanner
from trading.broker import PaperBroker
from trading.rebalance import RebalanceEngine


def main() -> None:
    # 股票池测试
    stocks = [
        {
            "code": "300394",
            "roe": 20,
            "alpha": 90,
        },
        {
            "code": "688568",
            "roe": 18,
            "alpha": 85,
        },
    ]
    # AI 基金团队扫描
    scanner = StockScanner(create_team())
    result = scanner.scan(stocks)
    pool = StockRanking().select(result)
    print("AI股票池:")
    print(pool)

    # 模拟交易：为股票池补仓
    broker = PaperBroker(capital=1000000)
    enriched = [
        {"code": r["code"], "price": 100.0, "score": r["score"]} for r in pool
    ]
    positions = RebalanceEngine().rebalance(enriched, broker)
    print("模拟持仓:")
    print(positions)
    print("剩余现金:")
    print(broker.cash)


if __name__ == "__main__":
    main()
