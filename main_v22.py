"""V2.2 运行入口：每日自动投资研究流水线（演示）。

注：V2.2 的因子打分扫描器与 V1.4 StockScanner 接口不同，
为避免破坏既有功能，以 StockScannerV22 落地，此处别名保持
ChatGPT 示例语义（StockScanner(market).scan()）。
"""

from automation.daily_pipeline import DailyPipeline
from scanner.stock_scanner import StockScannerV22 as StockScanner
from committee.voting import InvestmentCommittee

market = [
    {"code": "300394", "momentum": 1, "volume_ratio": 2, "fund_flow": 1},
    {"code": "688568", "momentum": 1, "volume_ratio": 1.8, "fund_flow": 1},
]

scanner = StockScanner(market)
committee = InvestmentCommittee()
pipeline = DailyPipeline(scanner, committee)
result = pipeline.run()
print(result)
