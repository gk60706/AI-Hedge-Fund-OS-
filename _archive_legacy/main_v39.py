from __future__ import annotations

import numpy as np
import pandas as pd

from alpha.search import AlphaSearchEngine
from alpha.library import AlphaLibrary
from validation.alpha_oos import AlphaOOSValidator
from alpha.evaluator import AlphaEvaluator


def create_demo_data(n=2000):
    rng = np.random.default_rng(42)
    data = pd.DataFrame(
        {
            "pe_inverse": rng.normal(0, 1, n),
            "pb_inverse": rng.normal(0, 1, n),
            "ps_inverse": rng.normal(0, 1, n),
            "momentum_20": rng.normal(0, 1, n),
            "momentum_60": rng.normal(0, 1, n),
            "momentum_120": rng.normal(0, 1, n),
            "roe": rng.normal(0, 1, n),
            "roic": rng.normal(0, 1, n),
            "revenue_growth": rng.normal(0, 1, n),
            "profit_growth": rng.normal(0, 1, n),
            "volatility_20": rng.normal(0, 1, n),
            "turnover": rng.normal(0, 1, n),
            "amount_20": rng.normal(0, 1, n),
        }
    )
    # 构造一个隐藏 Alpha
    hidden_alpha = (
        data["roe"] * 0.4
        + data["momentum_20"] * 0.3
        - data["volatility_20"] * 0.2
    )
    forward_return = (
        hidden_alpha * 0.01
        + rng.normal(0, 0.02, n)
    )
    return (
        data,
        pd.Series(forward_return, index=data.index),
    )


def main():
    print(
        "\n================================"
    )
    print(
        "AI Hedge Fund OS V3.9"
    )
    print(
        "AI Alpha Discovery Engine"
    )
    print(
        "================================\n"
    )
    features, returns = create_demo_data()
    engine = AlphaSearchEngine()
    library = AlphaLibrary(
        "experiments/" "results/" "alpha_library.json"
    )
    evaluator = AlphaEvaluator()
    population = engine.generate_candidates(
        size=300,
        depth=3,
    )
    generations = 10
    for generation in range(generations):
        print(
            f"\n===== Generation {generation + 1} ====="
        )
        results = engine.evaluate_candidates(
            population,
            features,
            returns,
        )
        if not results:
            print("No valid Alpha.")
            break
        champion = results[0]
        print("Champion:")
        print(champion["formula"])
        print("IC:", round(champion["ic"], 4))
        print("Complexity:", champion["complexity"])
        print(
            "Adjusted Score:",
            round(champion["adjusted_score"], 4),
        )
        champion["generation"] = generation + 1
        library.save(
            {
                "formula": champion["formula"],
                "ic": champion["ic"],
                "complexity": champion["complexity"],
                "adjusted_score": champion["adjusted_score"],
            }
        )
        population = (
            __import__(
                "evolution." "alpha_evolution",
                fromlist=["AlphaEvolution"],
            )
            .AlphaEvolution()
            .evolve(
                results,
                population_size=300,
            )
        )
    print(
        "\n=============================="
    )
    print("TOP ALPHA")
    print("==============================")
    for alpha in library.top(10):
        print(
            alpha["formula"],
            "IC=",
            round(alpha.get("ic", 0), 4),
        )


if __name__ == "__main__":
    main()
