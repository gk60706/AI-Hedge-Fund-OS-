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


# ============================================================
# V3.1 AI Portfolio Manager：Alpha 排名 + 组合优化 + 约束校验
# ============================================================
from typing import Any  # noqa: E402

from factors.alpha_score import AlphaScore  # noqa: E402
from portfolio.optimizer import PortfolioOptimizerV31 as PortfolioOptimizer  # noqa: E402
from portfolio.constraints import PortfolioConstraints  # noqa: E402


class PortfolioManagerV31:
    """V3.1 组合管理器：Alpha 排名 → 组合优化 → 约束校验。"""

    def __init__(
        self,
        max_positions: int = 10,
        max_single_weight: float = 0.20,
    ):
        self.max_positions = max_positions
        self.alpha = AlphaScore()
        self.optimizer = PortfolioOptimizer(
            max_positions=max_positions,
            max_single_weight=max_single_weight,
        )
        self.constraints = PortfolioConstraints(
            max_single_weight=max_single_weight,
        )

    def rank_candidates(
        self,
        stocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result = []
        for stock in stocks:
            stock = dict(stock)
            stock["alpha_score"] = self.alpha.calculate(stock)
            result.append(stock)
        return sorted(
            result,
            key=lambda x: x["alpha_score"],
            reverse=True,
        )

    def build_portfolio(
        self,
        stocks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ranked = self.rank_candidates(stocks)
        portfolio = self.optimizer.optimize(ranked)
        validation = self.constraints.validate(portfolio)
        if not validation["valid"]:
            raise ValueError(validation["reason"])
        return {
            "positions": portfolio,
            "validation": validation,
        }


# ============================================================
# V3.2 Dynamic Risk Budget：Portfolio Manager（升级版）
# ============================================================
from portfolio.optimizer import PortfolioOptimizerV32  # noqa: E402


class PortfolioManagerV32:
    """V3.2 动态风险预算组合管理器。"""

    def __init__(self):
        self.optimizer = PortfolioOptimizerV32()

    def build_portfolio(
        self,
        candidates,
        portfolio_volatility,
        max_drawdown,
        market_score,
        top_n=10,
    ):
        # Alpha 排名
        ranked = sorted(
            candidates,
            key=lambda x: x.get("alpha_score", 0),
            reverse=True,
        )
        selected = ranked[:top_n]
        result = self.optimizer.optimize(
            candidates=selected,
            portfolio_volatility=portfolio_volatility,
            max_drawdown=max_drawdown,
            market_score=market_score,
        )
        result["selected_stocks"] = [
            stock["code"]
            for stock in selected
        ]
        return result
