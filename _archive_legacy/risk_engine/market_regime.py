"""V2.5 市场状态识别：牛市 / 熊市 / 震荡。"""


class MarketRegime:
    """市场状态检测。"""

    def detect(self, index_change, volatility):
        if (index_change > 0.1 and volatility < 0.2):
            return "BULL"
        if volatility > 0.4:
            return "BEAR"
        return "SIDEWAY"
