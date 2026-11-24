"""V2.6 行业风险暴露分析：避免全部押注单一行业。"""


class ExposureAnalyzer:
    """按行业汇总仓位暴露。"""

    def analyze(self, positions):
        exposure = {}
        for stock, data in positions.items():
            sector = data["sector"]
            exposure[sector] = (
                exposure.get(sector, 0) + data["weight"]
            )
        return exposure
