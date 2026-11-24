"""V1.4 AI 精选股票池：取扫描结果前 N 名。"""


class StockRanking:
    """AI 精选股票池。"""

    def select(self, stocks: list, number: int = 20) -> list:
        return stocks[:number]
