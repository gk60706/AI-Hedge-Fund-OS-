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
