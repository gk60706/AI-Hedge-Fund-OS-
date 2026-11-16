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
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

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


@dataclass
class RetryPolicy:
    """单个助手提交报告的容错策略。

    ``attempts`` 是单个助手的最多提交次数（含首次）；
    ``timeout_seconds`` 为单次提交的墙钟上限，None 表示不限制。
    """

    attempts: int = 2
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("attempts must be >= 1")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive when set")


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
    failed_agents: dict[str, str] | None = None


# ============================================================
# 异常
# ============================================================


class AgentTimeoutError(TimeoutError):
    """单个助手在超时时间内没有交回报告。"""


class InsufficientAgentsError(RuntimeError):
    """成功提交的助手数量低于流水线要求的下限。"""

    def __init__(
        self,
        collected: int,
        required: int,
        failures: Mapping[str, str] | None = None,
    ) -> None:
        self.collected = collected
        self.required = required
        self.failures = dict(failures or {})
        detail = ", ".join(f"{k}: {v}" for k, v in self.failures.items()) or "none"
        super().__init__(
            f"only {collected} agent report(s) collected, "
            f"but {required} required (failures: {detail})"
        )


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
        self.min_reports = min_reports
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
        self.agent_failures: dict[str, str] = {}
        self.reports_submitted: int = 0

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
        retry_policy: RetryPolicy | None = None,
        allow_missing: bool = False,
    ) -> list[Any]:
        """逐个收集助手报告，带超时与重试。

        单个助手失败不会中断其他助手的提交；成功数量低于 ``min_reports``
        时，默认抛 ``InsufficientAgentsError``（显式降级），只有显式传入
        ``allow_missing=True`` 才继续往下走，并把缺口记进 outcome。
        """
        policy = retry_policy or RetryPolicy()
        records: list[Any] = []
        # 保留此前阶段（例如 API 生成）记录的失败，不被提交阶段覆盖
        prior_failures = dict(self.agent_failures)
        self.agent_failures = {}

        for report in reports:
            self.reports_submitted += 1
            record, error = self._submit_one(report, policy)
            if record is not None:
                records.append(record)
            else:
                self.agent_failures[report.agent_id] = (
                    f"{type(error).__name__}: {error}"
                )

        self.agent_failures = {**prior_failures, **self.agent_failures}

        if len(records) < self.min_reports and not allow_missing:
            raise InsufficientAgentsError(
                collected=len(records),
                required=self.min_reports,
                failures=self.agent_failures,
            )

        return records

    def _submit_one(
        self,
        report: AgentReport,
        policy: RetryPolicy,
    ) -> tuple[Any | None, BaseException | None]:
        last_error: BaseException | None = None

        for _ in range(policy.attempts):
            try:
                record = self._call_with_timeout(
                    lambda: self.report_collector.collect_report(
                        task_id=self.task_id,
                        agent_id=report.agent_id,
                        content=report.content,
                        title=report.title,
                        source=report.source,
                        notes=report.notes,
                        allow_incomplete=False,
                    ),
                    policy.timeout_seconds,
                    f"report submission for {report.agent_id}",
                )
                return record, None
            except BaseException as exc:  # noqa: BLE001 - 记录后按策略重试
                last_error = exc

        return None, last_error

    @staticmethod
    def _call_with_timeout(
        func: Callable[[], Any],
        timeout_seconds: float | None,
        description: str,
    ) -> Any:
        """在独立线程里执行一次调用，超出墙钟上限即抛 AgentTimeoutError。"""
        if not timeout_seconds:
            return func()

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(func)
            try:
                return future.result(timeout=timeout_seconds)
            except FutureTimeoutError as exc:
                raise AgentTimeoutError(
                    f"{description} exceeded {timeout_seconds}s"
                ) from exc

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
        retry_policy: RetryPolicy | None = None,
        allow_missing_agents: bool = False,
    ) -> ResearchOutcome:
        task_id = self.start_task(symbol, participants=participants)
        self.submit_reports(
            reports,
            retry_policy=retry_policy,
            allow_missing=allow_missing_agents,
        )
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
            failed_agents=dict(self.agent_failures),
        )

        if artifact_path:
            outcome.artifact_path = self.save_artifact(outcome, artifact_path)

        return outcome

    # --------------------------------------------------------
    # 7b. 真实 API 模式（适配器自动生成报告）
    # --------------------------------------------------------

    def run_live(
        self,
        symbol: str,
        registry: Any,
        *,
        as_of_date: str,
        reports_dir: str | Path,
        questions: str = "",
        debate: Any | None = None,
        ballots: Iterable[Any] | None = None,
        participants: Sequence[str] = DEFAULT_PARTICIPANTS,
        retry_policy: RetryPolicy | None = None,
        allow_missing_agents: bool = False,
        rationale: str = "",
    ) -> ResearchOutcome | dict[str, Any]:
        """调用真实 AI API 生成报告，再走后续链路。

        未配置的助手不会发请求，缺口写入 ``failed_agents``。
        没有提供辩论材料时只跑到「报告收集 + 交叉校验」，
        返回一个状态字典，避免伪造辩论与投票。
        """
        from ai_team.adapters import generate_reports as _generate

        task_id = self.start_task(symbol, participants=participants)

        reports_dir = Path(reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)

        generated, failures = _generate(
            registry,
            task_id=task_id,
            subject=symbol,
            ticker=symbol,
            as_of_date=as_of_date,
            questions=questions,
        )
        self.agent_failures.update(failures)

        for item in generated:
            (reports_dir / f"{item.agent_id}.md").write_text(
                item.content,
                encoding="utf-8",
            )

        audit = {
            "task_id": task_id,
            "symbol": symbol,
            "as_of_date": as_of_date,
            "registry": registry.describe()
            if hasattr(registry, "describe")
            else {},
            "generated": [item.to_dict() for item in generated],
            "failures": failures,
        }
        (reports_dir.parent / "generation.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        submitted = self.submit_reports(
            reports=[
                AgentReport(
                    agent_id=item.agent_id,
                    title=item.title,
                    content=item.content,
                    source=item.source,
                    notes=(
                        "Research only; not investment advice. "
                        f"content_sha256={item.record.content_sha256}"
                    ),
                )
                for item in generated
            ],
            retry_policy=retry_policy,
            allow_missing=allow_missing_agents,
        )
        validation = self.validate()

        if debate is None:
            return {
                "task_id": task_id,
                "symbol": symbol,
                "stage": "reports_collected",
                "reports_collected": len(submitted),
                "validation": _to_jsonable(validation),
                "generated": [item.to_dict() for item in generated],
                "failed_agents": dict(self.agent_failures),
                "artifact": str(reports_dir.parent / "generation.json"),
            }

        contributions = [
            DebateContribution(
                agent_id=item["agent_id"],
                position=item["position"],
                content=item["content"],
                evidence=list(item.get("evidence", [])),
            )
            for item in debate.get("contributions", [])
        ]
        debate_result = self.run_debate(
            contributions=contributions,
            conclusion=debate.get("conclusion", "partial_consensus"),
            conclusion_text=debate.get("conclusion_text", ""),
            unresolved_issues=debate.get("unresolved_issues", []),
            participants=participants,
        )
        consensus = self.build_consensus(participants=participants)
        decision = self.convene(rationale=rationale, ballots=ballots)

        return ResearchOutcome(
            task_id=task_id,
            symbol=symbol,
            validation=validation,
            debate=debate_result,
            consensus=consensus,
            decision=decision,
            failed_agents=dict(self.agent_failures),
        )

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
            "failed_agents": _to_jsonable(outcome.failed_agents or {}),
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
    parser.add_argument(
        "--debate",
        type=Path,
        default=None,
        help="debate.json; required unless --live is used",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="generate the reports by calling the configured AI APIs first",
    )
    parser.add_argument(
        "--as-of",
        dest="as_of",
        default=None,
        help="research date for the live prompt (default: today)",
    )
    parser.add_argument(
        "--questions",
        default="",
        help="extra questions appended to the live prompt",
    )
    parser.add_argument(
        "--adapter-timeout",
        type=float,
        default=120.0,
        help="HTTP timeout for one adapter call (default: 120s)",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--ballots", type=Path, default=None)
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=2,
        help="max submission attempts per agent (default: 2)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="wall-clock limit per agent submission (default: no limit)",
    )
    parser.add_argument(
        "--allow-missing-agents",
        action="store_true",
        help="continue with a degraded decision when fewer than min reports arrive",
    )
    args = parser.parse_args(argv)

    if not args.live and args.debate is None:
        parser.error("--debate is required unless --live is used")

    # ---------- 真实 API 模式 ----------
    if args.live:
        from ai_team.adapters import build_registry

        registry = build_registry(timeout=args.adapter_timeout)
        if not registry.adapters:
            print(
                json.dumps(
                    {
                        "stage": "no_adapter_configured",
                        "skipped": registry.skipped,
                        "hint": (
                            "在 .env 中配置 OPENAI_API_KEY / XAI_API_KEY / "
                            "HARK_BASE_URL 等后再运行 --live"
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2

        debate_payload = _load_debate(args.debate) if args.debate else None
        ballots = None
        if args.ballots:
            ballots = json.loads(args.ballots.read_text(encoding="utf-8"))

        live_pipeline = V310ResearchPipeline(project_root=args.project_root)
        result = live_pipeline.run_live(
            symbol=args.symbol,
            registry=registry,
            as_of_date=args.as_of or date.today().isoformat(),
            reports_dir=args.reports_dir,
            questions=args.questions,
            debate=debate_payload,
            ballots=ballots,
            retry_policy=RetryPolicy(
                attempts=args.retry_attempts,
                timeout_seconds=args.timeout_seconds,
            ),
            allow_missing_agents=args.allow_missing_agents,
        )

        if isinstance(result, dict):
            print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
            return 0

        print(
            json.dumps(
                {
                    "task_id": result.task_id,
                    "status": _read_value(result.decision, "status"),
                    "decision_id": _read_value(result.decision, "decision_id"),
                    "failed_agents": result.failed_agents or {},
                },
                ensure_ascii=False,
                default=str,
                indent=2,
            )
        )
        return 0

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
        retry_policy=RetryPolicy(
            attempts=args.retry_attempts,
            timeout_seconds=args.timeout_seconds,
        ),
        allow_missing_agents=args.allow_missing_agents,
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
                "failed_agents": outcome.failed_agents or {},
            },
            ensure_ascii=False,
            default=str,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
