"""V3.10 端到端压测：连续跑 N 次研究链路 + 进化断点续跑。

用法::

    python scripts/stress_v310_e2e.py --iterations 20
    python scripts/stress_v310_e2e.py --iterations 20 --workdir experiments/stress

每次迭代都会新建独立 project_root，避免任务 ID / 历史记录互相污染。
任一迭代失败会打印失败阶段并以非零退出码结束。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_team.research_pipeline import (  # noqa: E402
    AgentReport,
    DebateContribution,
    V310ResearchPipeline,
)

# evolution 依赖 numpy/pandas；只跑研究链路时不应强制安装这些依赖。
try:
    from evolution.alpha_evolution import (  # noqa: E402
        AlphaEvolutionConfig,
        AlphaEvolutionEngine,
    )
    from evolution.evolution_history import (  # noqa: E402
        EvolutionHistory,
        EvolutionHistoryConfig,
    )
    from evolution.fitness import (  # noqa: E402
        AlphaFitnessConfig,
        FitnessResult,
    )
    from evolution.population import (  # noqa: E402
        AlphaPopulation,
        AlphaPopulationConfig,
    )
    EVOLUTION_IMPORT_ERROR: Exception | None = None
except ImportError as exc:  # pragma: no cover - 依赖缺失分支
    EVOLUTION_IMPORT_ERROR = exc

SYMBOL = "300394"

REPORT_TEMPLATE = """# Executive Summary

The company is {stance} under the current evidence set.

# Key Findings

- Finding one: industry demand needs order-level confirmation.
- Finding two: margin trend should be verified against disclosures.

# Evidence and Sources

- Evidence: public disclosures and industry data.
- Evidence: no live quote or real-time data is used here.

# Analytical Reasoning

Industry growth does not automatically translate into earnings growth;
capacity, product mix, and customer concentration also matter.

# Risks and Limitations

- Demand may slow.
- Valuation may already price in optimistic expectations.

# Independent Conclusion

{conclusion}

# Confidence Level

{confidence}
"""


def build_reports() -> list[AgentReport]:
    return [
        AgentReport(
            agent_id="chatgpt",
            title="CIO research report",
            content=REPORT_TEMPLATE.format(
                stance="worth monitoring",
                conclusion="Maintain a watch position.",
                confidence="0.72",
            ),
        ),
        AgentReport(
            agent_id="grok",
            title="Market intelligence report",
            content=REPORT_TEMPLATE.format(
                stance="constructive but unconfirmed",
                conclusion="Continue monitoring pending order data.",
                confidence="0.76",
            ),
        ),
        AgentReport(
            agent_id="hark",
            title="Analyst research report",
            content=REPORT_TEMPLATE.format(
                stance="neutral",
                conclusion="No unconditional investment conclusion yet.",
                confidence="0.68",
            ),
        ),
    ]


def build_contributions() -> list[DebateContribution]:
    return [
        DebateContribution(
            agent_id="chatgpt",
            position="neutral",
            content="Valuation needs confirmation from earnings.",
            evidence=["Illustrative evidence only."],
        ),
        DebateContribution(
            agent_id="grok",
            position="support",
            content="Industry demand is a positive research direction.",
            evidence=["Illustrative evidence only."],
        ),
        DebateContribution(
            agent_id="hark",
            position="neutral",
            content="Continue monitoring, evidence is not conclusive.",
            evidence=["Illustrative evidence only."],
        ),
    ]


def build_ballots() -> list[dict[str, object]]:
    return [
        {
            "member_id": member_id,
            "vote": "approve",
            "rationale": "Research-only approval for monitoring.",
        }
        for member_id in (
            "cio",
            "risk",
            "quant",
            "fundamental",
            "industry",
            "compliance",
        )
    ]


class DeterministicFitness:
    """压测用确定性评估器（不读行情数据）。"""

    def __init__(self) -> None:
        self.config = AlphaFitnessConfig()

    def evaluate(self, genome, *, metrics=None, oos_metrics=None, apply_to_genome=True):
        score = (sum(ord(char) for char in genome.expression_string) % 1000) / 1000.0
        if apply_to_genome:
            genome.fitness = score
        return FitnessResult(
            genome_id=genome.genome_id,
            fitness=score,
            valid=True,
            component_scores={"test_score": score},
            weighted_score=score,
            accepted=False,
        )


def run_research_once(root: Path) -> dict[str, object]:
    pipeline = V310ResearchPipeline(project_root=root)
    artifact = root / "decision.json"
    outcome = pipeline.run(
        symbol=SYMBOL,
        reports=build_reports(),
        contributions=build_contributions(),
        conclusion="partial_consensus",
        conclusion_text="Agents agree the name deserves research, not a trade.",
        unresolved_issues=["Verify order growth."],
        rationale="Stress-test committee review.",
        ballots=build_ballots(),
        artifact_path=artifact,
    )
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    return {
        "task_id": outcome.task_id,
        "status": payload["decision"]["status"],
        "approval_score": payload["decision"].get("approval_score"),
        "quorum_met": payload["decision"].get("quorum_met"),
        "artifact": str(artifact),
    }


def make_engine(history_path: Path) -> AlphaEvolutionEngine:
    history = EvolutionHistory(
        config=EvolutionHistoryConfig(output_path=str(history_path)),
        run_id=f"stress-{history_path.stem}",
    )
    population = AlphaPopulation(
        config=AlphaPopulationConfig(population_size=8, elite_size=2, seed=12345)
    )
    population.initialize()
    return AlphaEvolutionEngine(
        population=population,
        research_evaluator=lambda genome: {"metrics": {"ic": 0.03}},
        fitness_evaluator=DeterministicFitness(),
        config=AlphaEvolutionConfig(
            max_generations=4, patience=None, experiment_name="stress"
        ),
        history=history,
    )


def run_evolution_resume_once(root: Path, index: int) -> dict[str, object]:
    reference = make_engine(root / f"reference-{index}.jsonl")
    reference.run(max_generations=4)
    reference_best = reference._best_fitness_seen
    reference_generation = reference.population.generation

    interrupted = make_engine(root / f"resume-{index}.jsonl")
    interrupted.run(max_generations=2)
    checkpoint = root / f"checkpoint-{index}.json"
    interrupted.save_checkpoint(checkpoint)

    resumed = AlphaEvolutionEngine.from_checkpoint(
        checkpoint,
        research_evaluator=lambda genome: {"metrics": {"ic": 0.03}},
        fitness_evaluator=DeterministicFitness(),
    )
    resumed.run(max_generations=2)

    return {
        "generation_matches": resumed.population.generation == reference_generation,
        "best_matches": abs((resumed._best_fitness_seen or 0.0) - (reference_best or 0.0)) < 1e-9,
        "generations": [
            report.generation for report in resumed.generation_reports
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--workdir", default="")
    parser.add_argument(
        "--skip-evolution",
        action="store_true",
        help="只压测 V3.10 研究链路（evolution 依赖 numpy/pandas）",
    )
    args = parser.parse_args()

    if args.iterations <= 0:
        parser.error("--iterations must be positive")

    if not args.skip_evolution and EVOLUTION_IMPORT_ERROR is not None:
        print(
            "evolution 模块不可用（缺少 numpy/pandas？）："
            f"{EVOLUTION_IMPORT_ERROR}；"
            "可加 --skip-evolution 只跑研究链路。",
            file=sys.stderr,
        )
        return 2

    workdir = (
        Path(args.workdir).resolve()
        if args.workdir
        else Path(tempfile.mkdtemp(prefix="v310_stress_"))
    )
    workdir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    started = time.perf_counter()

    for index in range(1, args.iterations + 1):
        root = workdir / f"research_{index:02d}"
        try:
            result = run_research_once(root)
        except Exception as exc:  # noqa: BLE001 - 压测要记录每一次失败
            failures.append(f"research#{index}: {type(exc).__name__}: {exc}")
            print(f"FAIL research #{index:02d} {type(exc).__name__}: {exc}")
            continue

        if result["status"] not in {"approved", "approved_with_conditions"}:
            failures.append(f"research#{index}: unexpected status {result['status']}")
        if not result["quorum_met"]:
            failures.append(f"research#{index}: quorum not met")
        print(
            f"PASS research #{index:02d} status={result['status']} "
            f"approval={result['approval_score']}"
        )

    evolution_iterations = 0 if args.skip_evolution else args.iterations
    for index in range(1, evolution_iterations + 1):
        try:
            result = run_evolution_resume_once(workdir, index)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"evolution#{index}: {type(exc).__name__}: {exc}")
            print(f"FAIL evolution #{index:02d} {type(exc).__name__}: {exc}")
            continue

        if not result["generation_matches"]:
            failures.append(f"evolution#{index}: generation mismatch")
        if not result["best_matches"]:
            failures.append(f"evolution#{index}: best fitness mismatch")
        print(
            f"PASS evolution #{index:02d} generations={result['generations']} "
            f"match={result['generation_matches'] and result['best_matches']}"
        )

    elapsed = time.perf_counter() - started
    total = args.iterations * (1 if args.skip_evolution else 2)
    print(
        f"\n{total - len(failures)}/{total} passed in {elapsed:.1f}s; "
        f"workdir={workdir}"
    )

    if failures:
        print("FAILURES:")
        for item in failures:
            print(f" - {item}")
        return 1

    if not args.workdir:
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
