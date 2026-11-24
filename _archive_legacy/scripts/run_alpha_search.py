
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main_v391 import make_demo_panel

from alpha.search import AlphaSearch


if __name__ == "__main__":
    panel = make_demo_panel()
    search = AlphaSearch(seed=42)
    results = search.search(panel, n_candidates=300)
    for result in results[:10]:
        print(
            result["expression"].to_string(),
            "| IC=", result["ic"],
            "| ICIR=", result["icir"],
            "| Q5-Q1=", result["q5_q1"],
        )
