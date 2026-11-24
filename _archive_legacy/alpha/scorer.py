from __future__ import annotations


class AlphaScorer:
    def score(
        self,
        mean_ic: float,
        icir: float,
        long_short: float,
        stability: float,
    ) -> float:
        score = (
            mean_ic * 30
            + icir * 20
            + long_short * 30
            + stability * 20
        )
        return float(score)

    def classify(
        self,
        score: float,
    ):
        if score >= 60:
            return "STRONG"
        if score >= 35:
            return "VALID"
        if score >= 15:
            return "WEAK"
        return "REJECT"
# ============================================================================
# V3.9.1 unified research engine - robust score (7-arg, dump)
# ============================================================================


def robust_score(ic, icir, qspread, positive_ratio, oos_ic, turnover, complexity):
    values = [ic, icir, qspread, positive_ratio, oos_ic]
    clean = []
    for value in values:
        if value is None or not math.isfinite(float(value)):
            clean.append(0.0)
        else:
            clean.append(float(value))
    ic_value, icir_value, q_value, positive_value, oos_value = clean
    score = (
        35 * ic_value
        + 15 * icir_value
        + 25 * q_value
        + 10 * (positive_value - 0.5)
        + 25 * oos_value
        - 2.0 * max(0.0, float(turnover))
        - 0.5 * float(complexity)
    )
    return float(score)


import math  # noqa: E402
