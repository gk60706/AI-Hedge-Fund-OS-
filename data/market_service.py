"""V1.4 行情服务：聚合数据源，输出最新快照。"""

from data.akshare_client import AkShareClient


class MarketService:
    """行情服务：拉取日线并取最新一根。"""

    def __init__(self):
        self.client = AkShareClient()

    def fetch_market(self, code: str) -> dict:
        data = self.client.get_daily_price(code)
        latest = data.iloc[-1]
        return {
            "code": code,
            "close": latest["收盘"],
            "volume": latest["成交量"],
        }
