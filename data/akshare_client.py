"""V1.4 AkShare 行情接口：A 股代码列表 + 日线行情。"""
import akshare as ak


class AkShareClient:
    """AkShare 数据客户端。"""

    def get_stock_list(self):
        """获取 A 股代码列表。"""
        df = ak.stock_info_a_code_name()
        return df

    def get_daily_price(self, code: str):
        """获取个股前复权日线行情。"""
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            adjust="qfq",
        )
        return df


from pathlib import Path

import pandas as pd


class AkShareClientV36:
    """V3.6 AkShare 数据中心：带本地 CSV 缓存的真实 A 股日线行情。

    第一原则：LLM 永远不能直接“猜”行情，AI 只能消费 Data Center 提供的数据。
    """

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_daily(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        code = code.strip()
        cache_file = self.cache_dir / f"{code}_{start_date}_{end_date}_{adjust}.csv"
        if cache_file.exists():
            df = pd.read_csv(cache_file, parse_dates=["日期"])
            return df
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        except Exception as exc:
            raise RuntimeError(f"AkShare 获取{code}历史数据失败:{exc}") from exc
        if df is None or df.empty:
            raise RuntimeError(f"{code}没有返回历史数据")
        df.to_csv(cache_file, index=False, encoding="utf-8-sig")
        return df
