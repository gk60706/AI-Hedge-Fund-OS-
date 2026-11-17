
"""
AI Hedge Fund OS V3.10
Multi-AI Collaboration Engine

Step 4: Cross Validator

Responsibilities:
- Parse reports collected by ReportCollector.
- Extract key findings and investment conclusions.
- Extract evidence and source references.
- Detect explicit positive/negative contradictions.
- Identify common claims across AI agents.
- Identify unsupported or weakly supported claims.
- Generate deterministic quality scores.
- Persist cross-validation results as JSON.
- Provide structured output for Step 5 Debate Engine.

Python >= 3.11
Production dependencies: Python standard library only.

No external AI APIs.
No network access.
No automated live trading.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


logger = logging.getLogger(__name__)


# ============================================================
# Exceptions
# ============================================================

class CrossValidatorError(Exception):
    """Base exception for cross validation."""


class CrossValidationTaskError(CrossValidatorError):
    """Task validation error."""


class CrossValidationReportError(CrossValidatorError):
    """Report loading or parsing error."""


class CrossValidationPersistenceError(CrossValidatorError):
    """Result persistence error."""


class InsufficientReportsError(CrossValidatorError):
    """Not enough reports for cross validation."""


class ValidationResultNotFoundError(CrossValidatorError):
    """Requested validation result does not exist."""


# ============================================================
# Enums
# ============================================================

class ClaimCategory(str, Enum):
    BUSINESS = "business"
    FINANCIAL = "financial"
    INDUSTRY = "industry"
    VALUATION = "valuation"
    GROWTH = "growth"
    RISK = "risk"
    INVESTMENT = "investment"
    OTHER = "other"


class ClaimDirection(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class ConflictSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceLevel(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    MISSING = "missing"


class ValidationStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


# ============================================================
# Constants
# ============================================================

DEFAULT_AGENTS = (
    "chatgpt",
    "grok",
    "hark",
)

DEFAULT_MIN_REPORTS = 2

DEFAULT_MIN_CLAIM_WORDS = 3

DEFAULT_COMMON_CLAIM_THRESHOLD = 2

DEFAULT_MAX_CLAIMS_PER_AGENT = 100

SECTION_ALIASES = {
    "key_findings": (
        "key findings",
        "key findings and analysis",
        "main findings",
        "主要发现",
        "核心发现",
        "关键发现",
        "核心观点",
    ),
    "evidence": (
        "evidence and sources",
        "evidence",
        "sources",
        "supporting evidence",
        "证据与来源",
        "证据",
        "数据来源",
        "信息来源",
    ),
    "reasoning": (
        "analytical reasoning",
        "analysis",
        "analysis and reasoning",
        "分析逻辑",
        "分析过程",
        "分析",
    ),
    "risks": (
        "risks and limitations",
        "risks",
        "risk factors",
        "风险与局限",
        "风险",
        "风险因素",
    ),
    "conclusion": (
        "independent conclusion",
        "conclusion",
        "investment conclusion",
        "final conclusion",
        "独立结论",
        "投资结论",
        "最终结论",
        "结论",
    ),
}

CATEGORY_KEYWORDS = {
    ClaimCategory.BUSINESS: (
        "business",
        "revenue",
        "product",
        "customer",
        "market share",
        "业务",
        "营收",
        "收入",
        "产品",
        "客户",
        "市场份额",
    ),
    ClaimCategory.FINANCIAL: (
        "cash flow",
        "profit",
        "margin",
        "debt",
        "earnings",
        "财务",
        "现金流",
        "利润",
        "毛利率",
        "负债",
        "净利润",
    ),
    ClaimCategory.INDUSTRY: (
        "industry",
        "competition",
        "supply",
        "demand",
        "capacity",
        "产业",
        "行业",
        "竞争",
        "供需",
        "产能",
    ),
    ClaimCategory.VALUATION: (
        "valuation",
        "pe",
        "pb",
        "peg",
        "multiple",
        "undervalued",
        "overvalued",
        "估值",
        "市盈率",
        "市净率",
        "低估",
        "高估",
    ),
    ClaimCategory.GROWTH: (
        "growth",
        "expansion",
        "future",
        "outlook",
        "增速",
        "增长",
        "扩张",
        "成长",
        "前景",
    ),
    ClaimCategory.RISK: (
        "risk",
        "uncertainty",
        "decline",
        "pressure",
        "风险",
        "不确定性",
        "下滑",
        "压力",
    ),
    ClaimCategory.INVESTMENT: (
        "buy",
        "sell",
        "hold",
        "bullish",
        "bearish",
        "recommendation",
        "买入",
        "卖出",
        "持有",
        "看多",
        "看空",
        "投资建议",
    ),
}

POSITIVE_KEYWORDS = (
    "positive",
    "bullish",
    "growth",
    "increase",
    "improve",
    "strong",
    "undervalued",
    "buy",
    "outperform",
    "看多",
    "利好",
    "增长",
    "提升",
    "改善",
    "强劲",
    "低估",
    "买入",
    "超预期",
    "上升",
)

NEGATIVE_KEYWORDS = (
    "negative",
    "bearish",
    "decline",
    "decrease",
    "weak",
    "overvalued",
    "risk",
    "sell",
    "underperform",
    "看空",
    "利空",
    "下降",
    "下滑",
    "疲弱",
    "高估",
    "卖出",
    "低于预期",
    "恶化",
)

NEGATION_KEYWORDS = (
    "not",
    "no",
    "never",
    "without",
    "isn't",
    "aren't",
    "doesn't",
    "don't",
    "无法",
    "没有",
    "并非",
    "不具备",
    "不存在",
    "不能",
    "不支持",
    "不看好",
    "未能",
)

EVIDENCE_KEYWORDS = (
    "source",
    "sources",
    "data",
    "report",
    "filing",
    "annual report",
    "quarterly report",
    "research",
    "official",
    "according to",
    "according",
    "数据",
    "来源",
    "年报",
    "季报",
    "公告",
    "财报",
    "研究报告",
    "官方",
    "根据",
    "披露",
)

HARD_EVIDENCE_PATTERNS = (
    r"https?://\S+",
    r"\b20\d{2}\b",
    r"\b\d+(?:\.\d+)?\s*%",
    r"\b\d+(?:\.\d+)?\s*(?:亿元|万元|亿|万|美元|元)\b",
    r"\b\d+(?:\.\d+)?\s*(?:billion|million|million yuan)\b",
)


# ============================================================
# Data models
# ============================================================

@dataclass
class ExtractedClaim:
    """One claim extracted from an AI report."""

    claim_id: str
    agent_id: str
    text: str

    category: str
    direction: str

    section: str

    evidence_level: str

    confidence: float = 0.0

    keywords: list[str] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentReportAnalysis:
    """Parsed report from one AI agent."""

    report_id: str
    task_id: str
    agent_id: str

    title: str

    claims: list[ExtractedClaim] = field(
        default_factory=list
    )

    sections: dict[str, str] = field(
        default_factory=dict
    )

    evidence_references: list[str] = field(
        default_factory=list
    )

    quality_score: float = 0.0

    evidence_score: float = 0.0

    warnings: list[str] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:

        return {
            "report_id": self.report_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "title": self.title,
            "claims": [
                item.to_dict()
                for item in self.claims
            ],
            "sections": self.sections,
            "evidence_references": self.evidence_references,
            "quality_score": self.quality_score,
            "evidence_score": self.evidence_score,
            "warnings": self.warnings,
        }


@dataclass
class AgentComparison:
    """Pairwise comparison between two AI agents."""

    agent_a: str
    agent_b: str

    common_claims: list[dict[str, Any]] = field(
        default_factory=list
    )

    conflicting_claims: list[dict[str, Any]] = field(
        default_factory=list
    )

    unmatched_claims: list[dict[str, Any]] = field(
        default_factory=list
    )

    agreement_score: float = 0.0

    conflict_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConflictFinding:
    """Detected disagreement between AI agents."""

    conflict_id: str

    category: str

    severity: str

    agent_a: str
    agent_b: str

    claim_a: str
    claim_b: str

    explanation: str

    resolution_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConsensusFinding:
    """A claim shared by multiple agents."""

    consensus_id: str

    category: str

    agents: list[str]

    representative_claim: str

    supporting_claims: list[str]

    support_count: int

    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CrossValidationResult:
    """Complete cross-validation result."""

    validation_id: str

    task_id: str

    status: str

    created_at: str

    report_count: int

    agent_analyses: list[AgentReportAnalysis] = field(
        default_factory=list
    )

    comparisons: list[AgentComparison] = field(
        default_factory=list
    )

    conflicts: list[ConflictFinding] = field(
        default_factory=list
    )

    consensus: list[ConsensusFinding] = field(
        default_factory=list
    )

    overall_quality_score: float = 0.0

    overall_evidence_score: float = 0.0

    agreement_score: float = 0.0

    warnings: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:

        return {
            "validation_id": self.validation_id,
            "task_id": self.task_id,
            "status": self.status,
            "created_at": self.created_at,
            "report_count": self.report_count,
            "agent_analyses": [
                item.to_dict()
                for item in self.agent_analyses
            ],
            "comparisons": [
                item.to_dict()
                for item in self.comparisons
            ],
            "conflicts": [
                item.to_dict()
                for item in self.conflicts
            ],
            "consensus": [
                item.to_dict()
                for item in self.consensus
            ],
            "overall_quality_score": self.overall_quality_score,
            "overall_evidence_score": self.overall_evidence_score,
            "agreement_score": self.agreement_score,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


# ============================================================
# Cross Validator
# ============================================================

class CrossValidator:
    """
    Deterministic multi-agent report cross validator.

    Dependencies:
        TaskManager
        ReportCollector

    Public interface:

        validate_task(task_id)
        analyze_report(record)
        extract_claims(agent_id, content)
        compare_agents(analysis_a, analysis_b)
        detect_conflicts(analyses)
        detect_consensus(analyses)
        save_result(result)
        get_result(validation_id)
        list_results(task_id=None)

    The algorithm is heuristic and does not claim
    semantic understanding or factual verification.
    """

    def __init__(
        self,
        task_manager: Any,
        report_collector: Any,
        storage_dir: Path | str | None = None,
        min_reports: int = DEFAULT_MIN_REPORTS,
        min_claim_words: int = DEFAULT_MIN_CLAIM_WORDS,
        common_claim_threshold: int = DEFAULT_COMMON_CLAIM_THRESHOLD,
        max_claims_per_agent: int = DEFAULT_MAX_CLAIMS_PER_AGENT,
    ) -> None:

        if task_manager is None:
            raise ValueError(
                "task_manager cannot be None."
            )

        if report_collector is None:
            raise ValueError(
                "report_collector cannot be None."
            )

        if min_reports < 1:
            raise ValueError(
                "min_reports must be at least 1."
            )

        if min_claim_words < 1:
            raise ValueError(
                "min_claim_words must be positive."
            )

        if common_claim_threshold < 2:
            raise ValueError(
                "common_claim_threshold must be at least 2."
            )

        if max_claims_per_agent < 1:
            raise ValueError(
                "max_claims_per_agent must be positive."
            )

        self.task_manager = task_manager
        self.report_collector = report_collector

        if storage_dir is None:
            storage_dir = (
                Path(report_collector.storage_dir)
                / "_cross_validation"
            )

        self.storage_dir = Path(
            storage_dir
        ).expanduser().resolve()

        self.storage_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.min_reports = min_reports
        self.min_claim_words = min_claim_words
        self.common_claim_threshold = common_claim_threshold
        self.max_claims_per_agent = max_claims_per_agent

    # --------------------------------------------------------
    # General utilities
    # --------------------------------------------------------

    @staticmethod
    def _now() -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _safe_id(
        value: str,
        field_name: str,
    ) -> str:

        if not isinstance(value, str):
            raise ValueError(
                f"{field_name} must be a string."
            )

        value = value.strip()

        if not re.fullmatch(
            r"[A-Za-z0-9_-]{1,120}",
            value,
        ):
            raise ValueError(
                f"Invalid {field_name}: {value}"
            )

        return value

    @staticmethod
    def _normalize_text(text: str) -> str:

        text = text.lower()

        text = re.sub(
            r"[^\w\u4e00-\u9fff]+",
            " ",
            text,
            flags=re.UNICODE,
        )

        return re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

    @staticmethod
    def _hash_text(text: str) -> str:

        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()[:12]

    @staticmethod
    def _score(value: float) -> float:

        return round(
            max(0.0, min(100.0, value)),
            2,
        )

    # --------------------------------------------------------
    # Section parsing
    # --------------------------------------------------------

    @staticmethod
    def _normalize_heading(line: str) -> str:

        line = line.strip()

        line = re.sub(
            r"^\s{0,3}#{1,6}\s*",
            "",
            line,
        )

        line = re.sub(
            r"^\s*(?:\d+[\.\)、:]|[-*+])\s*",
            "",
            line,
        )

        return line.strip().rstrip("#").strip().lower()

    def parse_sections(
        self,
        content: str,
    ) -> dict[str, str]:

        if not isinstance(content, str):
            raise CrossValidationReportError(
                "Report content must be a string."
            )

        alias_lookup = {}

        for section_name, aliases in SECTION_ALIASES.items():

            for alias in aliases:
                alias_lookup[alias.lower()] = section_name

        sections: dict[str, list[str]] = {}

        current_section = "preamble"

        sections[current_section] = []

        for line in content.splitlines():

            heading = self._normalize_heading(
                line
            )

            matched_section = alias_lookup.get(
                heading
            )

            if matched_section:

                current_section = matched_section

                sections.setdefault(
                    current_section,
                    [],
                )

                continue

            sections.setdefault(
                current_section,
                [],
            ).append(line)

        return {
            key: "\n".join(value).strip()
            for key, value in sections.items()
        }

    # --------------------------------------------------------
    # Claim classification
    # --------------------------------------------------------

    def classify_category(
        self,
        text: str,
    ) -> str:

        normalized = text.lower()

        # 财务类关键词优先于业务类：
        # “Revenue and profit growth” 应归为财务，而非业务。
        priority = (
            ClaimCategory.FINANCIAL,
            ClaimCategory.BUSINESS,
        )

        ordered_categories = [
            *priority,
            *(
                category
                for category in CATEGORY_KEYWORDS
                if category not in priority
            ),
        ]

        for category in ordered_categories:

            keywords = CATEGORY_KEYWORDS.get(
                category,
                (),
            )

            if any(
                keyword.lower() in normalized
                for keyword in keywords
            ):
                return category.value

        return ClaimCategory.OTHER.value

    def classify_direction(
        self,
        text: str,
    ) -> str:

        normalized = text.lower()

        positive_count = sum(
            normalized.count(keyword.lower())
            for keyword in POSITIVE_KEYWORDS
        )

        negative_count = sum(
            normalized.count(keyword.lower())
            for keyword in NEGATIVE_KEYWORDS
        )

        negation_count = sum(
            normalized.count(keyword.lower())
            for keyword in NEGATION_KEYWORDS
        )

        if positive_count == negative_count:
            return ClaimDirection.NEUTRAL.value

        if positive_count > negative_count:
            direction = ClaimDirection.POSITIVE.value
        else:
            direction = ClaimDirection.NEGATIVE.value

        # Simple negation handling.
        # This is intentionally conservative.
        if negation_count % 2 == 1:

            if direction == ClaimDirection.POSITIVE.value:
                direction = ClaimDirection.NEGATIVE.value

            elif direction == ClaimDirection.NEGATIVE.value:
                direction = ClaimDirection.POSITIVE.value

        return direction

    # --------------------------------------------------------
    # Evidence extraction
    # --------------------------------------------------------

    def extract_evidence_references(
        self,
        content: str,
    ) -> list[str]:

        if not isinstance(content, str):
            raise CrossValidationReportError(
                "Evidence source must be a string."
            )

        references = []

        for pattern in HARD_EVIDENCE_PATTERNS:

            matches = re.findall(
                pattern,
                content,
                flags=re.IGNORECASE,
            )

            references.extend(matches)

        for line in content.splitlines():

            normalized = line.lower()

            if any(
                keyword.lower() in normalized
                for keyword in EVIDENCE_KEYWORDS
            ):

                cleaned = line.strip()

                if cleaned:
                    references.append(cleaned[:500])

        # Keep insertion order and remove duplicates.
        return list(
            dict.fromkeys(references)
        )

    def assess_evidence(
        self,
        claim_text: str,
        evidence_section: str = "",
        evidence_references: Iterable[str] = (),
    ) -> str:

        combined = (
            claim_text
            + "\n"
            + evidence_section
        )

        references = list(
            evidence_references
        )

        has_hard_evidence = any(
            re.search(
                pattern,
                combined,
                flags=re.IGNORECASE,
            )
            for pattern in HARD_EVIDENCE_PATTERNS
        )

        has_source_language = any(
            keyword.lower() in combined.lower()
            for keyword in EVIDENCE_KEYWORDS
        )

        if has_hard_evidence and has_source_language:
            return EvidenceLevel.STRONG.value

        if has_hard_evidence:
            return EvidenceLevel.MODERATE.value

        if references or has_source_language:
            return EvidenceLevel.WEAK.value

        return EvidenceLevel.MISSING.value

    # --------------------------------------------------------
    # Claim extraction
    # --------------------------------------------------------

    def _split_claim_lines(
        self,
        content: str,
    ) -> list[str]:

        candidates = []

        for line in content.splitlines():

            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if re.fullmatch(
                r"[-=_*]{3,}",
                line,
            ):
                continue

            line = re.sub(
                r"^\s*(?:[-*+]|\d+[\.\)、:])\s*",
                "",
                line,
            ).strip()

            if not line:
                continue

            candidates.append(line)

        if not candidates and content.strip():
            candidates.append(
                content.strip()
            )

        return candidates

    def extract_claims(
        self,
        agent_id: str,
        content: str,
        evidence_section: str = "",
    ) -> list[ExtractedClaim]:

        agent_id = self._safe_id(
            agent_id,
            "agent_id",
        )

        if not isinstance(content, str):
            raise CrossValidationReportError(
                "Claim source must be a string."
            )

        claims = []

        lines = self._split_claim_lines(
            content
        )

        for index, line in enumerate(lines):

            normalized = self._normalize_text(
                line
            )

            words = normalized.split()

            if len(words) < self.min_claim_words:
                continue

            # Ignore lines that contain only generic labels.
            if normalized in {
                "summary",
                "analysis",
                "conclusion",
                "findings",
            }:
                continue

            category = self.classify_category(
                line
            )

            direction = self.classify_direction(
                line
            )

            evidence_level = self.assess_evidence(
                line,
                evidence_section,
            )

            claim_id = (
                f"CLM-{agent_id}-"
                + self._hash_text(
                    f"{agent_id}:{index}:{line}"
                )
            )

            keywords = [
                word
                for word in words
                if len(word) >= 2
            ][:20]

            confidence = 0.5

            if evidence_level == EvidenceLevel.STRONG.value:
                confidence += 0.3

            elif evidence_level == EvidenceLevel.MODERATE.value:
                confidence += 0.2

            elif evidence_level == EvidenceLevel.WEAK.value:
                confidence += 0.1

            claims.append(
                ExtractedClaim(
                    claim_id=claim_id,
                    agent_id=agent_id,
                    text=line,
                    category=category,
                    direction=direction,
                    section="extracted",
                    evidence_level=evidence_level,
                    confidence=round(
                        min(confidence, 1.0),
                        2,
                    ),
                    keywords=keywords,
                )
            )

            if len(claims) >= self.max_claims_per_agent:
                break

        return claims

    # --------------------------------------------------------
    # Report analysis
    # --------------------------------------------------------

    def analyze_report(
        self,
        record: Any,
    ) -> AgentReportAnalysis:

        try:

            report_id = self._safe_id(
                record.report_id,
                "report_id",
            )

            task_id = self._safe_id(
                record.task_id,
                "task_id",
            )

            agent_id = self._safe_id(
                record.agent_id,
                "agent_id",
            )

            content = self.report_collector.read_report(
                report_id
            )

        except Exception as exc:

            raise CrossValidationReportError(
                "Unable to load report for analysis."
            ) from exc

        sections = self.parse_sections(
            content
        )

        evidence_section = sections.get(
            "evidence",
            "",
        )

        evidence_references = self.extract_evidence_references(
            evidence_section
        )

        selected_content = "\n".join(
            [
                sections.get("key_findings", ""),
                sections.get("reasoning", ""),
                sections.get("risks", ""),
                sections.get("conclusion", ""),
            ]
        )

        if not selected_content.strip():
            selected_content = content

        claims = self.extract_claims(
            agent_id=agent_id,
            content=selected_content,
            evidence_section=evidence_section,
        )

        warnings = []

        if not sections.get("key_findings"):
            warnings.append(
                "Key findings section is missing."
            )

        if not sections.get("evidence"):
            warnings.append(
                "Evidence section is missing."
            )

        if not sections.get("conclusion"):
            warnings.append(
                "Independent conclusion section is missing."
            )

        if not claims:
            warnings.append(
                "No extractable claims found."
            )

        if not evidence_references:
            warnings.append(
                "No explicit evidence references detected."
            )

        claim_score = min(
            len(claims) / 5 * 100,
            100,
        )

        section_score = (
            sum(
                bool(sections.get(section))
                for section in (
                    "key_findings",
                    "evidence",
                    "reasoning",
                    "risks",
                    "conclusion",
                )
            )
            / 5
            * 100
        )

        evidence_score = self._calculate_evidence_score(
            claims
        )

        quality_score = (
            claim_score * 0.3
            + section_score * 0.4
            + evidence_score * 0.3
        )

        return AgentReportAnalysis(
            report_id=report_id,
            task_id=task_id,
            agent_id=agent_id,
            title=getattr(
                record,
                "title",
                "",
            ),
            claims=claims,
            sections=sections,
            evidence_references=evidence_references,
            quality_score=self._score(
                quality_score
            ),
            evidence_score=evidence_score,
            warnings=warnings,
        )

    # --------------------------------------------------------
    # Quality scoring
    # --------------------------------------------------------

    def _calculate_evidence_score(
        self,
        claims: list[ExtractedClaim],
    ) -> float:

        if not claims:
            return 0.0

        weights = {
            EvidenceLevel.STRONG.value: 100,
            EvidenceLevel.MODERATE.value: 70,
            EvidenceLevel.WEAK.value: 35,
            EvidenceLevel.MISSING.value: 0,
        }

        total = sum(
            weights.get(
                claim.evidence_level,
                0,
            )
            for claim in claims
        )

        return self._score(
            total / len(claims)
        )

    # --------------------------------------------------------
    # Claim similarity
    # --------------------------------------------------------

    def _claim_tokens(
        self,
        claim: ExtractedClaim,
    ) -> set[str]:

        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "this",
            "that",
            "from",
            "are",
            "was",
            "has",
            "have",
            "will",
            "can",
            "could",
            "should",
            "would",
            "公司",
            "目前",
            "认为",
            "我们",
            "认为",
            "可能",
            "因此",
            "但是",
            "以及",
            "对于",
        }

        return {
            token
            for token in self._normalize_text(
                claim.text
            ).split()
            if token not in stop_words
            and len(token) >= 2
        }

    def claim_similarity(
        self,
        claim_a: ExtractedClaim,
        claim_b: ExtractedClaim,
    ) -> float:

        if (
            claim_a.category != ClaimCategory.OTHER.value
            and claim_b.category != ClaimCategory.OTHER.value
            and claim_a.category != claim_b.category
        ):
            return 0.0

        tokens_a = self._claim_tokens(
            claim_a
        )

        tokens_b = self._claim_tokens(
            claim_b
        )

        if not tokens_a or not tokens_b:
            return 0.0

        union = tokens_a | tokens_b

        if not union:
            return 0.0

        intersection = tokens_a & tokens_b

        return len(intersection) / len(union)

    # --------------------------------------------------------
    # Conflict detection
    # --------------------------------------------------------

    def _is_conflict(
        self,
        claim_a: ExtractedClaim,
        claim_b: ExtractedClaim,
    ) -> bool:

        opposing_directions = {
            (
                ClaimDirection.POSITIVE.value,
                ClaimDirection.NEGATIVE.value,
            ),
            (
                ClaimDirection.NEGATIVE.value,
                ClaimDirection.POSITIVE.value,
            ),
        }

        if (
            claim_a.direction,
            claim_b.direction,
        ) not in opposing_directions:
            return False

        if claim_a.category != claim_b.category:
            return False

        return (
            self.claim_similarity(
                claim_a,
                claim_b,
            ) >= 0.20
        )

    def _conflict_severity(
        self,
        claim_a: ExtractedClaim,
        claim_b: ExtractedClaim,
    ) -> str:

        if claim_a.category == ClaimCategory.INVESTMENT.value:
            return ConflictSeverity.HIGH.value

        if claim_a.category in {
            ClaimCategory.FINANCIAL.value,
            ClaimCategory.VALUATION.value,
        }:
            return ConflictSeverity.HIGH.value

        if claim_a.category in {
            ClaimCategory.GROWTH.value,
            ClaimCategory.BUSINESS.value,
        }:
            return ConflictSeverity.MEDIUM.value

        return ConflictSeverity.LOW.value

    def _build_conflict(
        self,
        claim_a: ExtractedClaim,
        claim_b: ExtractedClaim,
    ) -> ConflictFinding:

        conflict_id = (
            "CNF-"
            + self._hash_text(
                claim_a.claim_id + claim_b.claim_id
            ).upper()
        )

        return ConflictFinding(
            conflict_id=conflict_id,
            category=claim_a.category,
            severity=self._conflict_severity(
                claim_a,
                claim_b,
            ),
            agent_a=claim_a.agent_id,
            agent_b=claim_b.agent_id,
            claim_a=claim_a.text,
            claim_b=claim_b.text,
            explanation=(
                "The two agents express opposite sentiment "
                "for claims classified in the same category "
                "with sufficient lexical overlap. "
                "This is a potential contradiction, not "
                "proof that either claim is false."
            ),
            resolution_required=True,
        )

    def detect_conflicts(
        self,
        analyses: list[AgentReportAnalysis],
    ) -> list[ConflictFinding]:

        conflicts = []

        for index, analysis_a in enumerate(analyses):

            for analysis_b in analyses[index + 1:]:

                for claim_a in analysis_a.claims:

                    for claim_b in analysis_b.claims:

                        if self._is_conflict(
                            claim_a,
                            claim_b,
                        ):

                            conflicts.append(
                                self._build_conflict(
                                    claim_a,
                                    claim_b,
                                )
                            )

        return conflicts

    # --------------------------------------------------------
    # Consensus detection
    # --------------------------------------------------------

    def detect_consensus(
        self,
        analyses: list[AgentReportAnalysis],
    ) -> list[ConsensusFinding]:

        groups: dict[
            tuple[str, str, str],
            list[ExtractedClaim]
        ] = {}

        all_claims = [
            claim
            for analysis in analyses
            for claim in analysis.claims
        ]

        for claim in all_claims:

            tokens = sorted(
                self._claim_tokens(claim)
            )

            if not tokens:
                continue

            key = (
                claim.category,
                claim.direction,
                " ".join(tokens),
            )

            groups.setdefault(
                key,
                [],
            ).append(claim)

        # Merge lexically similar claims.
        candidates = list(
            groups.items()
        )

        merged: list[list[ExtractedClaim]] = []

        used = set()

        for index, (key_a, claims_a) in enumerate(candidates):

            if index in used:
                continue

            cluster = list(claims_a)

            used.add(index)

            for other_index in range(
                index + 1,
                len(candidates),
            ):

                if other_index in used:
                    continue

                key_b, claims_b = candidates[
                    other_index
                ]

                if key_a[:2] != key_b[:2]:
                    continue

                representative_a = claims_a[0]
                representative_b = claims_b[0]

                if self.claim_similarity(
                    representative_a,
                    representative_b,
                ) >= 0.35:

                    cluster.extend(
                        claims_b
                    )

                    used.add(other_index)

            merged.append(cluster)

        findings = []

        for cluster in merged:

            unique_agents = sorted({
                claim.agent_id
                for claim in cluster
            })

            if len(unique_agents) < self.common_claim_threshold:
                continue

            supporting_claims = [
                claim.text
                for claim in cluster
            ]

            representative = max(
                cluster,
                key=lambda item: len(item.text),
            )

            average_confidence = sum(
                claim.confidence
                for claim in cluster
            ) / len(cluster)

            consensus_id = (
                "CON-"
                + self._hash_text(
                    "|".join(
                        sorted(
                            claim.claim_id
                            for claim in cluster
                        )
                    )
                ).upper()
            )

            findings.append(
                ConsensusFinding(
                    consensus_id=consensus_id,
                    category=representative.category,
                    agents=unique_agents,
                    representative_claim=representative.text,
                    supporting_claims=supporting_claims,
                    support_count=len(unique_agents),
                    confidence=round(
                        average_confidence,
                        2,
                    ),
                )
            )

        return findings

    # --------------------------------------------------------
    # Pairwise agent comparison
    # --------------------------------------------------------

    def compare_agents(
        self,
        analysis_a: AgentReportAnalysis,
        analysis_b: AgentReportAnalysis,
    ) -> AgentComparison:

        common_claims = []
        conflicting_claims = []
        unmatched_claims = []

        matched_b = set()

        for claim_a in analysis_a.claims:

            best_index = None
            best_similarity = 0.0

            for index, claim_b in enumerate(
                analysis_b.claims
            ):

                similarity = self.claim_similarity(
                    claim_a,
                    claim_b,
                )

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_index = index

            if (
                best_index is not None
                and best_similarity >= 0.35
            ):

                claim_b = analysis_b.claims[
                    best_index
                ]

                matched_b.add(
                    best_index
                )

                item = {
                    "claim_a": claim_a.text,
                    "claim_b": claim_b.text,
                    "similarity": round(
                        best_similarity,
                        4,
                    ),
                }

                if self._is_conflict(
                    claim_a,
                    claim_b,
                ):

                    conflicting_claims.append(
                        item
                    )

                else:

                    common_claims.append(
                        item
                    )

            else:

                unmatched_claims.append({
                    "agent_id": analysis_a.agent_id,
                    "claim": claim_a.text,
                })

        for index, claim_b in enumerate(
            analysis_b.claims
        ):

            if index not in matched_b:

                unmatched_claims.append({
                    "agent_id": analysis_b.agent_id,
                    "claim": claim_b.text,
                })

        total = (
            len(common_claims)
            + len(conflicting_claims)
            + len(unmatched_claims)
        )

        agreement_score = (
            len(common_claims) / total * 100
            if total else 0.0
        )

        return AgentComparison(
            agent_a=analysis_a.agent_id,
            agent_b=analysis_b.agent_id,
            common_claims=common_claims,
            conflicting_claims=conflicting_claims,
            unmatched_claims=unmatched_claims,
            agreement_score=self._score(
                agreement_score
            ),
            conflict_count=len(
                conflicting_claims
            ),
        )

    # --------------------------------------------------------
    # Overall agreement
    # --------------------------------------------------------

    def _calculate_agreement(
        self,
        comparisons: list[AgentComparison],
    ) -> float:

        if not comparisons:
            return 0.0

        return self._score(
            sum(
                item.agreement_score
                for item in comparisons
            ) / len(comparisons)
        )

    # --------------------------------------------------------
    # Main validation workflow
    # --------------------------------------------------------

    def validate_task(
        self,
        task_id: str,
        min_reports: int | None = None,
    ) -> CrossValidationResult:

        task_id = self._safe_id(
            task_id,
            "task_id",
        )

        required_reports = (
            self.min_reports
            if min_reports is None
            else min_reports
        )

        if (
            not isinstance(required_reports, int)
            or isinstance(required_reports, bool)
            or required_reports < 1
        ):
            raise ValueError(
                "min_reports must be an integer >= 1."
            )

        try:

            task = self.task_manager.get_task(
                task_id
            )

            records = self.report_collector.list_reports(
                task_id=task_id
            )

        except Exception as exc:

            raise CrossValidationTaskError(
                f"Unable to load task or reports: {task_id}"
            ) from exc

        if not records:

            raise InsufficientReportsError(
                f"No reports found for task: {task_id}"
            )

        if len(records) < required_reports:

            raise InsufficientReportsError(
                f"Expected at least {required_reports} reports; "
                f"found {len(records)}."
            )

        analyses = []

        for record in records:

            analyses.append(
                self.analyze_report(
                    record
                )
            )

        comparisons = []

        for index, analysis_a in enumerate(analyses):

            for analysis_b in analyses[index + 1:]:

                comparisons.append(
                    self.compare_agents(
                        analysis_a,
                        analysis_b,
                    )
                )

        conflicts = self.detect_conflicts(
            analyses
        )

        consensus = self.detect_consensus(
            analyses
        )

        quality_score = self._score(
            sum(
                item.quality_score
                for item in analyses
            ) / len(analyses)
        )

        evidence_score = self._score(
            sum(
                item.evidence_score
                for item in analyses
            ) / len(analyses)
        )

        agreement_score = self._calculate_agreement(
            comparisons
        )

        warnings = []

        if conflicts:
            warnings.append(
                f"{len(conflicts)} potential conflicts detected."
            )

        if not consensus:
            warnings.append(
                "No sufficiently supported common claims detected."
            )

        for analysis in analyses:
            warnings.extend(
                [
                    f"{analysis.agent_id}: {warning}"
                    for warning in analysis.warnings
                ]
            )

        status = ValidationStatus.SUCCESS.value

        if any(
            not analysis.claims
            for analysis in analyses
        ):
            status = ValidationStatus.PARTIAL.value

        if not comparisons:
            status = ValidationStatus.PARTIAL.value

        seats_active = [a.agent_id for a in analyses]
        seats_assigned = list(task.assignments.keys())
        seats_missing = [s for s in seats_assigned if s not in seats_active]
        multi_seat_performed = len(seats_active) >= 2

        if not multi_seat_performed:
            status = "not_performed"
            warnings.append(
                f"Multi-AI not performed: {len(seats_active)}/{len(seats_assigned) or len(seats_active)} seats reported."
            )
        elif seats_missing:
            warnings.append(f"Seats not reporting: {', '.join(seats_missing)}")

        validation_id = (
            "VAL-"
            + datetime.now(timezone.utc).strftime("%Y%m%d")
            + "-"
            + uuid.uuid4().hex[:10].upper()
        )

        result = CrossValidationResult(
            validation_id=validation_id,
            task_id=task_id,
            status=status,
            created_at=self._now(),
            report_count=len(records),
            agent_analyses=analyses,
            comparisons=comparisons,
            conflicts=conflicts,
            consensus=consensus,
            overall_quality_score=quality_score,
            overall_evidence_score=evidence_score,
            agreement_score=agreement_score,
            warnings=warnings,
            metadata={
                "task_title": task.title,
                "task_status": task.status,
                "agents": [
                    analysis.agent_id
                    for analysis in analyses
                ],
                "algorithm": "deterministic_heuristic_v1",
                "semantic_verification": False,
                "factual_verification": False,
                "seats_active": seats_active,
                "seats_assigned": seats_assigned,
                "seats_missing": seats_missing,
            },
        )

        logger.info(
            "Cross validation completed: task=%s "
            "reports=%s conflicts=%s consensus=%s",
            task_id,
            len(records),
            len(conflicts),
            len(consensus),
        )

        return result

    # --------------------------------------------------------
    # Persistence
    # --------------------------------------------------------

    def _result_path(
        self,
        validation_id: str,
    ) -> Path:

        validation_id = self._safe_id(
            validation_id,
            "validation_id",
        )

        return (
            self.storage_dir
            / f"{validation_id}.json"
        )

    def save_result(
        self,
        result: CrossValidationResult,
    ) -> Path:

        if not isinstance(
            result,
            CrossValidationResult,
        ):
            raise ValueError(
                "result must be CrossValidationResult."
            )

        path = self._result_path(
            result.validation_id
        )

        temporary_path = path.with_name(
            f".{path.name}.{uuid.uuid4().hex}.tmp"
        )

        try:

            serialized = json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                indent=4,
            )

            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:

                file.write(serialized)
                file.flush()

            temporary_path.replace(
                path
            )

            return path

        except (
            OSError,
            TypeError,
            ValueError,
        ) as exc:

            temporary_path.unlink(
                missing_ok=True
            )

            raise CrossValidationPersistenceError(
                "Unable to save cross-validation result."
            ) from exc

    # --------------------------------------------------------
    # Result retrieval
    # --------------------------------------------------------

    def get_result(
        self,
        validation_id: str,
    ) -> dict[str, Any]:

        path = self._result_path(
            validation_id
        )

        if not path.is_file():

            raise ValidationResultNotFoundError(
                f"Validation result not found: {validation_id}"
            )

        try:

            with path.open(
                "r",
                encoding="utf-8",
            ) as file:

                return json.load(file)

        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:

            raise CrossValidationPersistenceError(
                f"Unable to read result: {validation_id}"
            ) from exc

    # --------------------------------------------------------
    # Result listing
    # --------------------------------------------------------

    def list_results(
        self,
        task_id: str | None = None,
    ) -> list[dict[str, Any]]:

        if task_id is not None:
            task_id = self._safe_id(
                task_id,
                "task_id",
            )

        results = []

        for path in sorted(
            self.storage_dir.glob("VAL-*.json"),
            reverse=True,
        ):

            try:

                with path.open(
                    "r",
                    encoding="utf-8",
                ) as file:

                    data = json.load(file)

                if (
                    task_id is None
                    or data.get("task_id") == task_id
                ):
                    results.append(data)

            except (
                OSError,
                json.JSONDecodeError,
            ):

                logger.warning(
                    "Skipping invalid validation file: %s",
                    path,
                )

        return results

    # --------------------------------------------------------
    # Step 5 integration export
    # --------------------------------------------------------

    def export_debate_payload(
        self,
        result: CrossValidationResult,
    ) -> dict[str, Any]:

        if not isinstance(
            result,
            CrossValidationResult,
        ):
            raise ValueError(
                "result must be CrossValidationResult."
            )

        return {
            "task_id": result.task_id,
            "validation_id": result.validation_id,
            "conflicts": [
                item.to_dict()
                for item in result.conflicts
            ],
            "consensus": [
                item.to_dict()
                for item in result.consensus
            ],
            "agent_analyses": [
                {
                    "agent_id": item.agent_id,
                    "claims": [
                        claim.to_dict()
                        for claim in item.claims
                    ],
                    "quality_score": item.quality_score,
                    "evidence_score": item.evidence_score,
                }
                for item in result.agent_analyses
            ],
            "agreement_score": result.agreement_score,
            "warnings": result.warnings,
            "requires_debate": bool(
                result.conflicts
            ),
            "algorithm": "deterministic_heuristic_v1",
        }
