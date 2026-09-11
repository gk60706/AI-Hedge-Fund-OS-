"""V1.3 AI 投资委员会投票系统：基金经理观点表决。

V2.2 追加：InvestmentCommittee（Research/Quant/Macro/Risk/CIO 简单票决）。
"""


class VotingSystem:
    """AI 投票委员会。

    按各经理观点分数归类 BUY/HOLD/SELL，
    任一方向票数占比 >= 50% 时成为委员会决策。
    """

    def vote(self, opinions: list) -> dict:
        buy = 0
        hold = 0
        sell = 0
        for opinion in opinions:
            score = opinion["score"]
            if score >= 80:
                buy += 1
            elif score >= 60:
                hold += 1
            else:
                sell += 1
        total = len(opinions)
        if total == 0:
            return {"decision": "HOLD", "votes": {"BUY": 0, "HOLD": 0, "SELL": 0}}
        if buy / total >= 0.5:
            decision = "BUY"
        elif sell / total >= 0.5:
            decision = "SELL"
        else:
            decision = "HOLD"
        return {
            "decision": decision,
            "votes": {
                "BUY": buy,
                "HOLD": hold,
                "SELL": sell,
            },
        }


# ---------------------------------------------------------------------------
# V2.2 AI 投资委员会：多个 Agent 各自投票（BUY/SELL/HOLD），按票数定决策。
# ---------------------------------------------------------------------------
class InvestmentCommittee:
    """V2.2 投资委员会投票。"""

    def vote(self, opinions: list) -> str:
        """统计 BUY/SELL/HOLD 票数。

        Args:
            opinions: 字符串列表，如 ["BUY", "BUY", "HOLD", ...]。

        Returns:
            "BUY"（buy>=3）、"SELL"（sell>=3）、否则 "HOLD"。
        """
        buy = 0
        sell = 0
        hold = 0
        for opinion in opinions:
            if opinion == "BUY":
                buy += 1
            elif opinion == "SELL":
                sell += 1
            else:
                hold += 1
        if buy >= 3:
            return "BUY"
        if sell >= 3:
            return "SELL"
        return "HOLD"
