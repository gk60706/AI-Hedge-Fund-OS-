"""V1.3 AI 投资委员会投票系统：基金经理观点表决。"""


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
