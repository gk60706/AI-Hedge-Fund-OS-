"""V1.9 Alpha 评分系统：机构级多指标评分。"""


class AlphaScore:
    """综合收益 / Sharpe / 回撤 / 胜率 计算 Alpha 分数。"""

    def calculate(self, result: dict) -> float:
        """Args:
            result: 含 return / sharpe / drawdown / win_rate 的评价结果。

        Returns:
            Alpha 分数。
        """
        score = (
            result["return"] * 40
            + result["sharpe"] * 30
            - abs(result["drawdown"]) * 20
            + result["win_rate"] * 10
        )
        return score
