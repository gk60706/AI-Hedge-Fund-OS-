"""V2.6 组合管理器：持仓权重总览。"""


class PortfolioManager:
    """组合管理器。"""

    def __init__(self):
        self.positions = {}

    def add_position(self, code, weight):
        self.positions[code] = weight

    def total_weight(self):
        return sum(self.positions.values())

    def check(self):
        return {
            "positions": self.positions,
            "total": self.total_weight(),
        }

# ============================================================
# V3.0 AI Autonomous Hedge Fund：Portfolio Manager
# ============================================================
class PortfolioManagerV30:
    def __init__(
        self,
        max_positions: int = 10,
        max_single_weight: float = 0.20,
    ):
        self.max_positions = max_positions
        self.max_single_weight = (
            max_single_weight
        )

    def build_targets(
        self,
        decisions: list,
    ) -> list:
        buys = [
            item
            for item
            in decisions
            if item.get("decision")
            == "BUY"
        ]
        buys.sort(
            key=lambda x:
            x.get("weighted_score",
                  -999),
            reverse=True,
        )
        buys = buys[
            : self.max_positions
        ]
        if not buys:
            return []
        base_weight = min(
            self.max_single_weight, 1.0
            / len(buys),
        )
        targets = []
        for item in buys:
            targets.append({
                "code": item["code"],
                "target_weight": base_weight,
                "score": item.get(
                    "weighted_score", 0
                ),
            })
        return targets
