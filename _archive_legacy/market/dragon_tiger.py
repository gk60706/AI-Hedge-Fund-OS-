"""V1.5 龙虎榜 Agent：机构抢筹识别。"""


class DragonTigerAgent:
    """龙虎榜分析 Agent。"""

    def analyze(self, data: dict) -> dict:
        institutions = data.get("institution_buy", 0)
        if institutions > 10000000:
            return {
                "signal": "机构抢筹",
                "score": 90,
            }
        return {
            "signal": "普通交易",
            "score": 50,
        }
