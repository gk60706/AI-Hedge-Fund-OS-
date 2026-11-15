# ai_team/research_pipeline.py

"""V3.10 多 AI 协作研究流水线。

把 ai_team 里的七个模块串成一条可复用的研究链路：

    config -> task_manager -> report_collector -> cross_validator
           -> debate_engine -> consensus_engine -> investment_committee

只做研究与治理，不产生任何实盘交易指令。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ai_team.config import TeamConfig, get_default_config
from ai_team.consensus_engine import ConsensusEngine
from ai_team.cross_validator import CrossValidator
from ai_team.debate_engine import (
    DebateConclusion,
    DebateEngine,
    DebatePosition,
)
from ai_team.investment_committee import InvestmentCommittee
from ai_team.report_collector import ReportCollector
from ai_team.task_manager import TaskManager


DEFAULT_PARTICIPANTS = ("chatgpt", "grok", "hark")


# ============================================================
# 输入数据模型
# ============================================================


@dataclass
class AgentReport:
    """单个 AI 助手提交的独立研究报告。"""

    agent_id: str
    title: str
    content: str
    source: str = "ai_team_pipeline"
    notes: str = "Research only; not investment advice."


@dataclass
class DebateContribution:
    """辩论阶段某个助手的发言。"""

    agent_id: str
    position: str
    content: str
    evidence: list[str]


# ============================================================
# 输出数据模型
# ============================================================


@dataclass
class ResearchOutcome:
    task_id: str
    symbol: str
    validation: Any
    debate: Any
    consensus: Any
    decision: Any
    artifact_path: Path | None = None


# ============================================================
# 工具函数
# ============================================================


def _read_value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _identifier(obj: Any, *names: str) -> str:
    for name in names:
        value = _read_value(obj, name)
        if value:
            return str(value)
    raise ValueError(f"object {type(obj).__name__} has none of {names}")


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if hasattr(value, "to_dict"):
        return _to_jsonable(value.to_dict())
    if hasattr(value, "__dict__"):
        return _to_jsonable(vars(value))
    return str(value)


# ============================================================
# 流水线
# ============================================================


class V310ResearchPipeline:
    """把 V3.10 的七个模块装配成一条端到端研究流水线。"""

    def __init__(
        self,
        project_root: str | Path | None = None,
        min_reports: int = 2,
        max_rounds: int = 1,
    ) -> None:
        self.config: TeamConfig = get_default_config(project_root=project_root)
        self.config.create_directories()
        storage = self.config.evaluation_dir / "v310_pipeline"

        self.task_manager = TaskManager(
            config=self.config,
            storage_dir=self.config.tasks_dir,
        )
        self.report_collector = ReportCollector(
            task_manager=self.task_manager,
            storage_dir=self.config.reports_dir,
            strict_validation=False,
        )
        self.cross_validator = CrossValidator(
            task_manager=self.task_manager,
            report_collector=self.report_collector,
            storage_dir=storage / "validation",
            min_reports=min_reports,
        )
        self.debate_engine = DebateEngine(
            task_manager=self.task_manager,
            cross_validator=self.cross_validator,
            report_collector=self.report_collector,
            storage_dir=storage / "debates",
            default_max_rounds=max_rounds,
        )
        self.consensus_engine = ConsensusEngine(
            task_manager=self.task_manager,
            cross_validator=self.cross_validator,
            debate_engine=self.debate_engine,
            storage_dir=storage / "consensus",
        )
        self.investment_committee = InvestmentCommittee(
            task_manager=self.task_manager,
            consensus_engine=self.consensus_engine,
            storage_dir=storage / "committee",
        )

        self._task_id: str | None = None
        self._validation = None
        self._debate = None
        self._consensus = None

    # --------------------------------------------------------
    # 1. 建任务
    # --------------------------------------------------------

    def start_task(
        self,
        symbol: str,
        title: str | None = None,
        description: str | None = None,
        participants: Sequence[str] = DEFAULT_PARTICIPANTS,
    ) -> str:
        task = self.task_manager.create_task(
            title=title or f"V3.10 research: {symbol}",
            description=description
            or (
                f"Multi-AI research on {symbol}. "
                "Research governance only; no trade execution."
            ),
            task_type="stock_research",
            priority="high",
            target=symbol,
            requirements=[
                "Independent research from each agent",
                "Cross-agent validation",
                "Debate and consensus",
                "Investment committee review",
            ],
            expected_outputs=[
                "Independent research reports",
                "Cross-validation result",
                "Debate result",
                "Consensus report",
                "Investment committee decision",
            ],
            metadata={"paper_trade_only": True},
            created_by="v310_research_pipeline",
        )

        task_id = _identifier(task, "task_id")

        self.task_manager.assign_task(
            task_id,
            agent_ids=list(participants),
        )
        self.task_manager.start_task(task_id)

        self._task_id = task_id
        return task_id

    @property
    def task_id(self) -> str:
        if not self._task_id:
            raise RuntimeError("start_task must run before this stage")
        return self._task_id

    # --------------------------------------------------------
    # 2. 收报告
    # --------------------------------------------------------

    def submit_reports(
        self,
        reports: Iterable[AgentReport],
    ) -> list[Any]:
        records = []

        for report in reports:
            records.append(
                self.report_collector.collect_report(
                    task_id=self.task_id,
                    agent_id=report.agent_id,
                    content=report.content,
                    title=report.title,
                    source=report.source,
                    notes=report.notes,
                    allow_incomplete=False,
                )
            )

        return records

    # --------------------------------------------------------
    # 3. 交叉校验
    # --------------------------------------------------------

    def validate(self) -> Any:
        self._validation = self.cross_validator.validate_task(self.task_id)
        return self._validation

    # --------------------------------------------------------
    # 4. 辩论
    # --------------------------------------------------------

    def run_debate(
        self,
        contributions: Iterable[DebateContribution],
        conclusion: str,
        conclusion_text: str,
        unresolved_issues: Iterable[str] | None = None,
        participants: Sequence[str] = DEFAULT_PARTICIPANTS,
        force: bool = True,
    ) -> Any:
        if self._validation is None:
            self.validate()

        session = self.debate_engine.start_debate(
            task_id=self.task_id,
            validation_result=self._validation,
            participants=list(participants),
            force=force,
        )
        debate_id = _identifier(session, "debate_id")

        for item in contributions:
            self.debate_engine.submit_response(
                debate_id=debate_id,
                agent_id=item.agent_id,
                content=item.content,
                position=DebatePosition(item.position),
                evidence=list(item.evidence),
            )

        self._debate = self.debate_engine.finalize_debate(
            debate_id=debate_id,
            conclusion=DebateConclusion(conclusion),
            conclusion_text=conclusion_text,
            unresolved_issues=list(unresolved_issues or []),
        )
        return self._debate

    # --------------------------------------------------------
    # 5. 共识
    # --------------------------------------------------------

    def build_consensus(
        self,
        participants: Sequence[str] = DEFAULT_PARTICIPANTS,
        force: bool = False,
    ) -> Any:
        if self._debate is None:
            raise RuntimeError("run_debate must run before build_consensus")

        self._consensus = self.consensus_engine.build_consensus(
            task_id=self.task_id,
            validation_result=self._validation,
            debate=self._debate,
            participants=list(participants),
            force=force,
        )
        return self._consensus

    # --------------------------------------------------------
    # 6. 投委会决议
    # --------------------------------------------------------

    def convene(
        self,
        rationale: str = "",
        ballots: Iterable[Any] | None = None,
        force: bool = False,
    ) -> Any:
        if self._consensus is None:
            raise RuntimeError("build_consensus must run before convene")

        return self.investment_committee.convene(
            task_id=self.task_id,
            consensus_report=self._consensus,
            ballots=ballots,
            rationale=rationale,
            force=force,
        )

    # --------------------------------------------------------
    # 7. 端到端
    # --------------------------------------------------------

    def run(
        self,
        symbol: str,
        reports: Iterable[AgentReport],
        contributions: Iterable[DebateContribution],
        conclusion: str,
        conclusion_text: str,
        unresolved_issues: Iterable[str] | None = None,
        participants: Sequence[str] = DEFAULT_PARTICIPANTS,
        rationale: str = "",
        ballots: Iterable[Any] | None = None,
        artifact_path: str | Path | None = None,
    ) -> ResearchOutcome:
        task_id = self.start_task(symbol, participants=participants)
        self.submit_reports(reports)
        validation = self.validate()
        debate = self.run_debate(
            contributions=contributions,
            conclusion=conclusion,
            conclusion_text=conclusion_text,
            unresolved_issues=unresolved_issues,
            participants=participants,
        )
        consensus = self.build_consensus(participants=participants)
        decision = self.convene(rationale=rationale, ballots=ballots)

        outcome = ResearchOutcome(
            task_id=task_id,
            symbol=symbol,
            validation=validation,
            debate=debate,
            consensus=consensus,
            decision=decision,
        )

        if artifact_path:
            outcome.artifact_path = self.save_artifact(outcome, artifact_path)

        return outcome

    # --------------------------------------------------------
    # 8. 落盘
    # --------------------------------------------------------

    def save_artifact(
        self,
        outcome: ResearchOutcome,
        path: str | Path,
    ) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "symbol": outcome.symbol,
            "task_id": outcome.task_id,
            "validation": _to_jsonable(outcome.validation),
            "debate": _to_jsonable(outcome.debate),
            "consensus": _to_jsonable(outcome.consensus),
            "decision": _to_jsonable(outcome.decision),
        }

        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target


# ============================================================
# 命令行入口
# ============================================================


def _load_reports(reports_dir: Path) -> list[AgentReport]:
    reports = []

    for path in sorted(reports_dir.glob("*.md")):
        reports.append(
            AgentReport(
                agent_id=path.stem,
                title=f"{path.stem} research report",
                content=path.read_text(encoding="utf-8"),
                source="ai_team_cli",
            )
        )

    if not reports:
        raise SystemExit(f"no *.md reports found in {reports_dir}")

    return reports


def _load_debate(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the V3.10 multi-AI research pipeline.",
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--reports-dir", required=True, type=Path)
    parser.add_argument("--debate", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--ballots", type=Path, default=None)
    parser.add_argument("--project-root", type=Path, default=None)
    args = parser.parse_args(argv)

    debate_payload = _load_debate(args.debate)
    contributions = [
        DebateContribution(
            agent_id=item["agent_id"],
            position=item["position"],
            content=item["content"],
            evidence=list(item.get("evidence", [])),
        )
        for item in debate_payload.get("contributions", [])
    ]

    ballots = None
    if args.ballots:
        ballots = json.loads(args.ballots.read_text(encoding="utf-8"))

    pipeline = V310ResearchPipeline(project_root=args.project_root)
    outcome = pipeline.run(
        symbol=args.symbol,
        reports=_load_reports(args.reports_dir),
        contributions=contributions,
        conclusion=debate_payload.get("conclusion", "partial_consensus"),
        conclusion_text=debate_payload.get("conclusion_text", ""),
        unresolved_issues=debate_payload.get("unresolved_issues", []),
        rationale=debate_payload.get("rationale", ""),
        ballots=ballots,
        artifact_path=args.output,
    )

    decision = outcome.decision
    print(
        json.dumps(
            {
                "task_id": outcome.task_id,
                "status": _read_value(decision, "status"),
                "decision_id": _read_value(decision, "decision_id"),
                "artifact": str(outcome.artifact_path)
                if outcome.artifact_path
                else None,
            },
            ensure_ascii=False,
            default=str,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
