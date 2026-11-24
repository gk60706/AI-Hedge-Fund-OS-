"""V2.6 AI 股票评分系统：基本面 30% + 技术面 20% + 资金流 30% + 行业景气 20%。"""


class AIStockScore:
    """综合评分。"""

    def calculate(self, stock):
        score = (
            stock["fundamental"] * 0.3
            + stock["technical"] * 0.2
            + stock["capital"] * 0.3
            + stock["industry"] * 0.2
        )
        return round(score, 2)
