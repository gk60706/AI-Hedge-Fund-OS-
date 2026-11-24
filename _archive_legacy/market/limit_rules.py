"""V3.6 LimitRule：A 股涨跌停规则。

按代码前缀判断涨跌幅限制：
- 主板（60/00）：10%
- 创业板（30）：20%
- 科创板（68）：20%
- 北交所（43/83/87）：30%

注意：真实市场还需要处理 ST、*ST、上市首日、特殊交易状态等，
不能仅凭代码前缀判断（V3.7 完善）。
"""

from __future__ import annotations


class LimitRule:
    def __init__(self, default_limit=0.10):
        self.default_limit = default_limit

    def limit_pct(self, code: str) -> float:
        # 主板普通股票默认 10%
        if code.startswith(("60", "00")):
            return 0.10
        # 创业板
        if code.startswith("30"):
            return 0.20
        # 科创板
        if code.startswith("68"):
            return 0.20
        # 北交所
        if code.startswith(("43", "83", "87")):
            return 0.30
        return self.default_limit

    def is_limit_up(self, prev_close: float, price: float, code: str) -> bool:
        if prev_close <= 0:
            return False
        limit = self.limit_pct(code)
        return price >= prev_close * (1 + limit - 0.002)

    def is_limit_down(self, prev_close: float, price: float, code: str) -> bool:
        if prev_close <= 0:
            return False
        limit = self.limit_pct(code)
        return price <= prev_close * (1 - limit + 0.002)


# ============================================================================
# V3.9.1 unified research engine - module-level limit helpers
# ============================================================================


def limit_pct(code: str) -> float:
    """A 股涨跌幅限制：创业板/科创板 20%，北交所 30%，其余 10%。"""
    if code.startswith(("30", "68")):
        return 0.20
    if code.startswith(("43", "83", "87")):
        return 0.30
    return 0.10


def limit_prices(prev_close: float, pct: float) -> tuple:
    return (round(prev_close * (1 + pct), 2), round(prev_close * (1 - pct), 2))


def is_limit_up(prev_close, price, code, tolerance: float = 1e-6) -> bool:
    if prev_close <= 0:
        return False
    up, _ = limit_prices(prev_close, limit_pct(code))
    return price >= up - tolerance


def is_limit_down(prev_close, price, code, tolerance: float = 1e-6) -> bool:
    if prev_close <= 0:
        return False
    _, down = limit_prices(prev_close, limit_pct(code))
    return price <= down + tolerance
