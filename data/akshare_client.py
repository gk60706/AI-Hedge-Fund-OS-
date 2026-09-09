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
