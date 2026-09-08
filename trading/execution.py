"""交易执行引擎 (V0.7)

将交易信号转为模拟订单并经 PaperBroker 成交。
"""
from trading.broker import PaperBroker
from trading.order import Order

broker = PaperBroker()


def execute_trade(signal: dict) -> dict:
    """执行模拟交易。

    :param signal: 含 ``code``/``action``/``price``/``volume`` 的交易信号
    :return: PaperBroker 成交结果
    """
    order = Order(
        code=signal["code"],
        action=signal["action"],
        price=signal["price"],
        volume=signal["volume"],
    )
    result = broker.execute(order)
    return result
