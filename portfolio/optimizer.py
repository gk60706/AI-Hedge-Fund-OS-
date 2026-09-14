"""股票组合优化 (V0.6)

简化版 Markowitz 最优化：基于收益协方差矩阵求最小方差组合权重。
"""
import numpy as np


def markowitz_optimizer(returns) -> list:
    """简化版 Markowitz 组合优化。

    :param returns: 收益矩阵（每行一只股票的时间序列收益）
    :return: 组合权重列表（和为 1）
    """
    cov = np.cov(returns)
    inv = np.linalg.inv(cov)
    weights = inv.sum(axis=1)
    weights = weights / weights.sum()
    return weights.tolist()


# ============================================================
# V3.1 AI Portfolio Manager：Alpha 加权组合优化（保留 10% 现金）
# ============================================================
from typing import Any  # noqa: E402


class PortfolioOptimizerV31:
    """V3.1 组合优化器。

    按 Alpha 分数加权分配权重，单票受 max_single_weight 限制，
    系统主动保留 10% 现金（不强制满仓）。
    """

    def __init__(
        self,
        max_positions: int = 10,
        max_single_weight: float = 0.20,
        cash_reserve: float = 0.10,
    ):
        self.max_positions = max_positions
        self.max_single_weight = max_single_weight
        self.cash_reserve = cash_reserve

    def optimize(
        self,
        ranked: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """对已按 Alpha 排序的候选股生成组合。

        Args:
            ranked: 按 alpha_score 降序排列的候选列表。

        Returns:
            持仓列表（每项含 code/name/weight/alpha_score/volatility）。
        """
        selected = ranked[: self.max_positions]
        if not selected:
            return []
        total_alpha = sum(
            max(float(s.get("alpha_score", 0.0)), 0.0)
            for s in selected
        )
        budget = 1.0 - self.cash_reserve
        positions = []
        if total_alpha <= 0:
            base = min(budget / len(selected), self.max_single_weight)
            for s in selected:
                positions.append(
                    {**s, "weight": round(base, 4)}
                )
        else:
            for s in selected:
                raw = (
                    budget
                    * max(float(s.get("alpha_score", 0.0)), 0.0)
                    / total_alpha
                )
                weight = min(raw, self.max_single_weight)
                positions.append(
                    {**s, "weight": round(weight, 4)}
                )
        return positions


# ============================================================
# V3.2 Dynamic Risk Budget：Risk Parity + Alpha + 行业/Beta/回撤/波动率目标
# ============================================================
from portfolio.risk_parity import RiskParity  # noqa: E402
from portfolio.volatility_target import VolatilityTarget  # noqa: E402
from portfolio.industry_budget import IndustryRiskBudget  # noqa: E402
from portfolio.beta_control import BetaController  # noqa: E402
from risk.drawdown_control import DrawdownController  # noqa: E402


class PortfolioOptimizerV32:
    """V3.2 动态风险预算组合优化器。

    流程：Risk Parity → Alpha 调整 → 归一化 → 行业预算 → Beta 控制
          → 波动率目标 → 回撤控制 → 市场状态 → 最终仓位与现金。
    """

    def __init__(self):
        self.risk_parity = RiskParity()
        self.volatility_target = VolatilityTarget(
            target_volatility=0.15,
            min_exposure=0.20,
            max_exposure=0.95,
        )
        self.industry_budget = IndustryRiskBudget(
            default_max_weight=0.30,
        )
        self.beta_controller = BetaController(
            target_beta=0.85,
            max_beta=1.10,
        )
        self.drawdown_controller = DrawdownController()

    def optimize(
        self,
        candidates: list[dict[str, Any]],
        portfolio_volatility: float,
        max_drawdown: float,
        market_score: float,
    ) -> dict[str, Any]:
        """动态风险预算组合优化。

        Args:
            candidates: 候选股（含 code/volatility/alpha_score/industry/beta）。
            portfolio_volatility: 当前组合年化波动率。
            max_drawdown: 当前最大回撤（负数）。
            market_score: 市场评分（0-100）。

        Returns:
            {"positions", "cash", "exposure", "portfolio_volatility",
             "max_drawdown", "market_score", "drawdown_multiplier"}。
        """
        if not candidates:
            return {
                "positions": {},
                "cash": 1.0,
                "exposure": 0.0,
            }

        # ------------------------------------------------
        # 1. 提取波动率
        # ------------------------------------------------
        volatilities = {}
        for stock in candidates:
            code = stock["code"]
            volatilities[code] = max(
                stock.get("volatility", 0.20),
                0.01,
            )

        # ------------------------------------------------
        # 2. Risk Parity
        # ------------------------------------------------
        weights = self.risk_parity.calculate_weights(
            volatilities,
            max_weight=0.20,
        )

        # ------------------------------------------------
        # 3. Alpha 调整
        # ------------------------------------------------
        alpha_map = {
            stock["code"]: stock.get("alpha_score", 50.0)
            for stock in candidates
        }
        for code in weights:
            alpha = alpha_map.get(code, 50.0)
            # Alpha 50 = 1.0 / Alpha 80 = 1.3 / Alpha 30 = 0.7
            adjustment = 0.5 + alpha / 100.0
            weights[code] *= adjustment

        # ------------------------------------------------
        # 4. Normalize
        # ------------------------------------------------
        total = sum(weights.values())
        if total > 0:
            weights = {
                code: weight / total
                for code, weight in weights.items()
            }

        # ------------------------------------------------
        # 5. Industry Risk Budget
        # ------------------------------------------------
        industries = {
            stock["code"]: stock.get("industry", "UNKNOWN")
            for stock in candidates
        }
        weights = self.industry_budget.apply(weights, industries)

        # ------------------------------------------------
        # 6. Beta Control
        # ------------------------------------------------
        betas = {
            stock["code"]: stock.get("beta", 1.0)
            for stock in candidates
        }
        weights = self.beta_controller.adjust(weights, betas)

        # ------------------------------------------------
        # 7. Volatility Targeting
        # ------------------------------------------------
        exposure = self.volatility_target.calculate_exposure(
            portfolio_volatility,
        )

        # ------------------------------------------------
        # 8. Drawdown Control
        # ------------------------------------------------
        drawdown_multiplier = (
            self.drawdown_controller.calculate_exposure_multiplier(
                max_drawdown,
            )
        )
        exposure *= drawdown_multiplier

        # ------------------------------------------------
        # 9. Market Regime
        # ------------------------------------------------
        if market_score < 30:
            exposure *= 0.50
        elif market_score < 40:
            exposure *= 0.70
        elif market_score < 50:
            exposure *= 0.85
        exposure = max(
            0.0,
            min(0.95, exposure),
        )

        # ------------------------------------------------
        # 10. 最终仓位
        # ------------------------------------------------
        positions = {
            code: weight * exposure
            for code, weight in weights.items()
        }

        # ------------------------------------------------
        # 11. 现金
        # ------------------------------------------------
        cash = 1.0 - sum(positions.values())
        return {
            "positions": positions,
            "cash": cash,
            "exposure": exposure,
            "portfolio_volatility": portfolio_volatility,
            "max_drawdown": max_drawdown,
            "market_score": market_score,
            "drawdown_multiplier": drawdown_multiplier,
        }



# ============================================================
# V3.4 机构级 Ensemble Portfolio Optimizer（MV + RP + BL + Alpha）
# ============================================================
import numpy as np  # noqa: E402
from optimization.mean_variance import MeanVarianceOptimizer  # noqa: E402
from optimization.risk_parity import RiskParityOptimizer  # noqa: E402
from optimization.black_litterman import BlackLittermanModel  # noqa: E402
from optimization.ensemble import EnsembleOptimizer  # noqa: E402
from risk.constraints import RiskConstraintEngine  # noqa: E402


class InstitutionalPortfolioOptimizer:
    """V3.4 机构级组合优化器。

    流程：Mean-Variance → Risk Parity → Black-Litterman → Alpha
          → Ensemble 融合 → 单票权重上限 → 归一化。
    """

    def __init__(self):
        self.mv = MeanVarianceOptimizer()
        self.rp = RiskParityOptimizer()
        self.bl = BlackLittermanModel()
        self.ensemble = EnsembleOptimizer()
        self.constraints = RiskConstraintEngine()

    def optimize(
        self,
        codes,
        covariance,
        expected_returns,
        alpha_scores,
        market_weights=None,
        views=None,
        confidence=None,
    ):
        """机构级组合优化。

        Args:
            codes: 股票代码列表。
            covariance: 协方差矩阵。
            expected_returns: 预期收益向量。
            alpha_scores: 代码 -> Alpha 分数。
            market_weights: 市值权重（默认等权）。
            views: Black-Litterman 观点（默认 = expected_returns）。
            confidence: 观点置信度（默认 0.5）。

        Returns:
            代码 -> 权重 dict。
        """
        n = len(codes)
        if n == 0:
            return {}

        covariance = np.asarray(covariance, dtype=float)
        if market_weights is None:
            market_weights = np.ones(n) / n
        if views is None:
            views = np.array(expected_returns, dtype=float)
        if confidence is None:
            confidence = np.ones(n) * 0.5

        # -----------------------------
        # Mean Variance
        # -----------------------------
        mv_weights = self.mv.optimize(
            expected_returns={
                code: expected_returns[i]
                for i, code in enumerate(codes)
            },
            covariance=covariance,
            codes=codes,
        )

        # -----------------------------
        # Risk Parity
        # -----------------------------
        rp_weights = self.rp.optimize(
            covariance=covariance,
            codes=codes,
        )

        # -----------------------------
        # Black-Litterman
        # -----------------------------
        posterior = self.bl.calculate_posterior_returns(
            covariance=covariance,
            market_weights=market_weights,
            views=views,
            view_confidence=confidence,
        )
        bl_raw = {
            code: max(float(posterior[i]), 0.0)
            for i, code in enumerate(codes)
        }
        total_bl = sum(bl_raw.values())
        if total_bl > 0:
            bl_weights = {
                code: value / total_bl
                for code, value in bl_raw.items()
            }
        else:
            bl_weights = {code: 1.0 / n for code in codes}

        # -----------------------------
        # Ensemble
        # -----------------------------
        final_weights = self.ensemble.combine(
            mean_variance=mv_weights,
            risk_parity=rp_weights,
            black_litterman=bl_weights,
            alpha_scores=alpha_scores,
        )

        # -----------------------------
        # 单票限制
        # -----------------------------
        final_weights = {
            code: min(weight, self.constraints.max_single_weight)
            for code, weight in final_weights.items()
        }
        total = sum(final_weights.values())
        if total > 0:
            final_weights = {
                code: weight / total
                for code, weight in final_weights.items()
            }
        return final_weights
