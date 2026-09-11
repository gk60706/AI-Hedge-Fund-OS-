"""V1.8 AkShare 真实行情数据加载模块。

从 AkShare 拉取 A 股历史日线行情，列名统一为英文。
"""

import akshare as ak
import pandas as pd


class AkShareLoader:
    """AkShare 真实行情数据加载器。"""

    def load_daily(self, symbol: str) -> pd.DataFrame:
        """加载单只股票的历史日线（前复权）。

        Args:
            symbol: 股票代码，如 "600519"。

        Returns:
            含 date / close / volume / high / low 列的 DataFrame。
        """
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            adjust="qfq",
        )
        df = df.rename(
            columns={
                "日期": "date",
                "收盘": "close",
                "成交量": "volume",
                "最高": "high",
                "最低": "low",
            }
        )
        return df

    def load_batch(self, stocks: list[str]) -> dict[str, pd.DataFrame]:
        """批量加载多只股票行情，单只失败不中断。

        Args:
            stocks: 股票代码列表。

        Returns:
            {code: DataFrame} 字典。
        """
        result: dict[str, pd.DataFrame] = {}
        for code in stocks:
            try:
                result[code] = self.load_daily(code)
            except Exception as e:  # noqa: BLE001 - 单只失败继续
                print(code, e)
        return result
