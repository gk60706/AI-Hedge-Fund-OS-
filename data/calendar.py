"""V3.6 TradingCalendar：交易日历接口。

V3.6 先提供接口；后续生产版应直接接入中国交易所实际交易日历，
并处理春节 / 国庆 / 元旦 / 清明 / 劳动节 / 临时休市等节假日。
"""

from __future__ import annotations

import pandas as pd


class TradingCalendar:
    @staticmethod
    def business_days(start_date: str, end_date: str):
        return pd.bdate_range(start=start_date, end=end_date)

    @staticmethod
    def is_trading_day(date, trading_days):
        date = pd.Timestamp(date)
        return date in set(pd.to_datetime(trading_days))
