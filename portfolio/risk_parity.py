"""V3.2 Risk Parity：按波动率倒数分配风险贡献。"""

from __future__ import annotations


class RiskParity:
    """风险平价：让每只股票承担接近的风险，而非等额资金。"""

    def calculate_weights(
        self,
        volatilities: dict[str, float],
        max_weight: float = 0.20,
    ) -> dict[str, float]:
        """按波动率倒数计算风险平价权重。

        Args:
            volatilities: {code: volatility}。
            max_weight: 单票权重上限。

        Returns:
            {code: weight}（归一化到总和 1）。
        """
        if not volatilities:
            return {}
        inverse_vol = {}
        for code, volatility in volatilities.items():
            volatility = max(float(volatility), 1e-6)
            inverse_vol[code] = 1.0 / volatility
        total = sum(inverse_vol.values())
        weights = {
            code: value / total
            for code, value in inverse_vol.items()
        }
        # 单票上限
        weights = {
            code: min(weight, max_weight)
            for code, weight in weights.items()
        }
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {
                code: weight / total_weight
                for code, weight in weights.items()
            }
        return weights
