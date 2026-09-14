from __future__ import annotations

import numpy as np
import pandas as pd

from factors.factory import (
    FactorFactory,
)
from experiments.factor_test import (
    FactorExperiment,
)
from experiments.experiment import (
    ExperimentStore,
)


def create_demo_data(
    n=1000,
):
    rng = np.random.default_rng(42)
    close = pd.Series(
        100 * np.cumprod(
            1 + rng.normal(0.0004, 0.015, n,)
        )
    )
    data = pd.DataFrame(
        {
            "close": close,
            "pe": rng.uniform(5, 100, n,),
            "pb": rng.uniform(0.5, 10, n,),
            "ps": rng.uniform(0.5, 20, n,),
            "roe": rng.normal(0.10, 0.05, n,),
            "roic": rng.normal(0.08, 0.04, n,),
            "revenue_growth": rng.normal(0.15, 0.20, n,),
            "profit_growth": rng.normal(0.15, 0.30, n,),
            "turnover": rng.uniform(0.5, 10, n,),
            "amount": rng.uniform(1e7, 1e9, n,),
        }
    )
    return data


def main():
    print(
        "\n=============================="
    )
    print(
        "AI Hedge Fund OS V3.8"
    )
    print(
        "AI Alpha Research Engine"
    )
    print(
        "=============================="
    )
    data = create_demo_data()
    factors = FactorFactory.default_factors()
    experiment = FactorExperiment()
    store = ExperimentStore()
    results = {}
    for factor in factors:
        try:
            values = (
                factor.calculate(data)
            )
            forward_return = (
                data["close"].shift(-5)
                / data["close"]
                - 1
            )
            result = (
                experiment.run(
                    factor=values,
                    forward_return=forward_return,
                    ic_history=[],
                )
            )
            results[factor.name] = result
            print(
                "\nFactor:", factor.name,
            )
            print(
                "IC:", round(result["ic"], 4,),
            )
            print(
                "ICIR:", round(result["icir"], 4,),
            )
            print(
                "Long-Short:", round(result["long_short"], 4,),
            )
            print(
                "Score:", round(result["score"], 2,),
            )
            print(
                "Class:", result["classification"],
            )
        except Exception as exc:
            print(
                f"{factor.name} ERROR:", exc,
            )
    path = store.save(
        "factor_experiment",
        results,
    )
    print(
        "\nExperiment saved:", path,
    )


if __name__ == "__main__":
    main()
