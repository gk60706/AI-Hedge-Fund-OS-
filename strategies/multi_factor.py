"""多因子模型 (V0.6)

动量 40% + 价值 30% + 资金 30% 融合为 Alpha 评分。
"""
from strategies.momentum_strategy import momentum_score
from strategies.value_strategy import value_score
from strategies.capital_strategy import capital_score


def calculate_factor(stock: dict) -> dict:
    """计算单只股票的多因子 Alpha。

    :param stock: 含 ``code``/``return_30``/``pe``/``buy_volume``/``sell_volume`` 的 dict
    :return: ``{"code", "alpha", "factor_detail": {momentum, value, capital}}``
    """
    momentum = momentum_score(stock)
    value = value_score(stock)
    capital = capital_score(stock)
    alpha = momentum * 0.4 + value * 0.3 + capital * 0.3
    return {
        "code": stock["code"],
        "alpha": alpha,
        "factor_detail": {
            "momentum": momentum,
            "value": value,
            "capital": capital,
        },
    }
