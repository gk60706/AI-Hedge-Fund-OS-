from __future__ import annotations

import pandas as pd


class AlphaOOSValidator:
    def validate(
        self,
        expression,
        evaluator,
        train_features,
        train_returns,
        test_features,
        test_returns,
    ):
        train_signal = evaluator.evaluate(
            expression,
            train_features,
        )
        test_signal = evaluator.evaluate(
            expression,
            test_features,
        )
        train_data = pd.concat(
            [
                train_signal.rename("factor"),
                train_returns.rename("return"),
            ],
            axis=1,
        ).dropna()
        test_data = pd.concat(
            [
                test_signal.rename("factor"),
                test_returns.rename("return"),
            ],
            axis=1,
        ).dropna()
        if len(train_data) < 30:
            return {
                "passed": False,
                "reason": "TRAIN_TOO_SHORT",
            }
        if len(test_data) < 30:
            return {
                "passed": False,
                "reason": "TEST_TOO_SHORT",
            }
        train_ic = train_data["factor"].corr(
            train_data["return"],
            method="spearman",
        )
        test_ic = test_data["factor"].corr(
            test_data["return"],
            method="spearman",
        )
        passed = (
            abs(test_ic) >= 0.02
            and (
                train_ic == 0
                or abs(test_ic) >= abs(train_ic) * 0.30
            )
        )
        return {
            "passed": bool(passed),
            "train_ic": float(train_ic),
            "oos_ic": float(test_ic),
        }
