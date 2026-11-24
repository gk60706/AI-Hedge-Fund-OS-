"""Quant Agent (V0.9)

融合 Alpha 因子分与资金分，输出量化信号分。
"""


def quant_signal(stock: dict) -> dict:
    """量化信号。

    :param stock: 含 ``code``/``alpha``/``fund_score`` 的股票 dict
    :return: ``{"code", "quant_score"}``
    """
    score = 0
    score += stock.get("alpha", 0)
    score += stock.get("fund_score", 0)
    score /= 2
    return {"code": stock["code"], "quant_score": score}
