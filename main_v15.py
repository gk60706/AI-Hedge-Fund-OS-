"""V1.5 实时盘中交易入口：五档盘口 + 主力资金 → AI 盘中决策。

研究/模拟用途，输出决策信号，不接入任何真实交易通道。
"""

from capital.main_force import MainForceDetector
from intraday.trader_agent import IntradayTrader
from realtime.orderbook import OrderBookAnalyzer


def main() -> None:
    orderbook = OrderBookAnalyzer()
    capital = MainForceDetector()
    trader = IntradayTrader()

    tick = {
        "bid1_volume": 50000,
        "bid2_volume": 40000,
        "bid3_volume": 30000,
        "bid4_volume": 20000,
        "bid5_volume": 10000,
        "ask1_volume": 10000,
        "ask2_volume": 10000,
        "ask3_volume": 10000,
        "ask4_volume": 10000,
        "ask5_volume": 10000,
    }
    book_signal = orderbook.analyze(tick)
    capital_signal = {"main_force_score": 90}

    decision = trader.decide(
        [
            book_signal["strength"] * 30,
            capital_signal["main_force_score"],
            80,
        ]
    )
    print("AI盘中交易决定:", decision)


if __name__ == "__main__":
    main()
