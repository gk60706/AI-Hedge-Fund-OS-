"""V2.3 运行入口：资金雷达 + 盘口分析 → 盘中交易决策（演示）。

注：V2.3 的同步版 WebSocket 客户端与 V0.8 异步版同名类接口不同，
为避免破坏既有功能，以 MarketWebSocketV23 落地（本入口未直接使用）。
"""

from realtime.radar.capital_radar import CapitalRadar
from realtime.radar.orderbook_analyzer import OrderBookAnalyzer
from realtime.trading.intraday_agent import IntradayTrader

market = {
    "volume_ratio": 3,
    "buy_amount": 800000,
    "sell_amount": 300000,
    "price_change": 2,
}

orderbook = {
    "bid": [10000, 9000, 8000],
    "ask": [3000, 2000, 1000],
}

radar = CapitalRadar()
book = OrderBookAnalyzer()
trader = IntradayTrader()

capital_signal = radar.analyze(market)
order_signal = book.analyze(orderbook)
decision = trader.decide(capital_signal, order_signal)

print(capital_signal)
print(order_signal)
print(decision)
