"""因子融合引擎 (V0.5)

将多因子结果融合为 Alpha 评分，并对股票池按 Alpha 排名。
"""
from factors.momentum import momentum_factor


def calculate_alpha(df) -> float:
    """对单只股票行情计算 Alpha 评分（当前为动量因子简版融合）。"""
    df = momentum_factor(df)
    latest = df.iloc[-1]
    score = 0
    # 动量
    if latest["momentum"] > 0:
        score += 40
    else:
        score += 20
    return score


def rank_stocks(stocks: list) -> list:
    """按 ``alpha`` 字段从高到低排序股票列表。

    :param stocks: 元素为 dict、含 ``alpha`` 键的列表
    """
    return sorted(stocks, key=lambda x: x["alpha"], reverse=True)
