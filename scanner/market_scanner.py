"""V3.0.2 主扫描器：MarketData 全市场 → StockScanner 候选。"""
from __future__ import annotations

from data.market_data import MarketData
from scanner.stock_scanner import StockScannerV302 as StockScanner


class MarketScanner:
    def __init__(self):
        self.data = MarketData()
        self.scanner = StockScanner()

    def run(self, limit: int = 100):
        df = self.data.get_all_spot()
        return self.scanner.scan_dataframe(
            df,
            limit=limit,
        )
