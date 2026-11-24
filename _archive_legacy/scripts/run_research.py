
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import get_settings
from main_v391 import make_demo_panel
from research.pipeline import ResearchPipeline
from research.report import write_report


def main():
    settings = get_settings()
    panel = make_demo_panel(
        n_stocks=80,
        n_days=900,
        seed=settings.random_seed,
    )
    pipeline = ResearchPipeline(seed=settings.random_seed)
    result = pipeline.run(
        panel=panel,
        train_end="2024-01-31",
        oos_start="2024-02-01",
        n_candidates=300,
    )
    report_path = write_report(
        result,
        settings.report_dir / "V3.9.1_research_report.md",
    )
    print()
    print("===== CHAMPION =====")
    print(result.champion)
    print()
    print("===== AUDIT =====")
    print(result.audit)
    print()
    print("===== BACKTEST =====")
    print(result.backtest_metrics)
    print()
    print("Report:", report_path)


if __name__ == "__main__":
    main()
