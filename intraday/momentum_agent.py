"""盘中动量 Agent - 涨停检测 (V0.8)

按涨幅判断是否触发涨停信号。
"""


def limit_up_agent(price: float, yesterday_close: float) -> dict:
    """涨停检测。

    :param price: 当前价
    :param yesterday_close: 昨日收盘价
    :return: ``{"signal": "LIMIT_UP"|"NORMAL", "score": 100|50}``
    """
    change = (price / yesterday_close - 1) * 100
    if change >= 9.8:
        return {"signal": "LIMIT_UP", "score": 100}
    return {"signal": "NORMAL", "score": 50}
