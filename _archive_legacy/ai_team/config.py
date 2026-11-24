
"""
AI Hedge Fund OS V3.10
Multi-AI Collaboration Engine

Step 1: Team Configuration

Python >= 3.11
No API required in free collaboration mode.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict


class CollaborationMode(str, Enum):
    FREE_MANUAL = "free_manual"
    HYBRID = "hybrid"
    API_AUTOMATION = "api_automation"


class ProjectMode(str, Enum):
    INVESTMENT = "investment"
    GENERAL = "general"
    BOTH = "both"


class AgentRole(str, Enum):
    CIO = "cio"
    INTELLIGENCE = "intelligence"
    ANALYST = "analyst"


@dataclass(frozen=True)
class AgentConfig:
    name: str
    platform: str
    role: AgentRole
    responsibilities: tuple[str, ...]
    independent_analysis: bool = True
    requires_api: bool = False


@dataclass(frozen=True)
class TeamConfig:
    project_root: Path
    collaboration_mode: CollaborationMode
    project_mode: ProjectMode
    agents: Dict[str, AgentConfig]

    @property
    def team_dir(self) -> Path:
        return self.project_root / "ai_team"

    @property
    def prompts_dir(self) -> Path:
        return self.team_dir / "prompts"

    @property
    def tasks_dir(self) -> Path:
        return self.team_dir / "tasks"

    @property
    def reports_dir(self) -> Path:
        return self.team_dir / "reports"

    @property
    def evaluation_dir(self) -> Path:
        return self.team_dir / "evaluation"

    @property
    def schemas_dir(self) -> Path:
        return self.team_dir / "schemas"

    @property
    def tests_dir(self) -> Path:
        return self.project_root / "tests" / "ai_team"

    @property
    def api_enabled(self) -> bool:
        return (
            self.collaboration_mode
            == CollaborationMode.API_AUTOMATION
        )

    @property
    def manual_handoff_required(self) -> bool:
        return (
            self.collaboration_mode
            == CollaborationMode.FREE_MANUAL
        )

    def create_directories(self) -> None:
        """Create all AI team directories."""

        directories = [
            self.team_dir,
            self.prompts_dir,
            self.tasks_dir,
            self.reports_dir,
            self.evaluation_dir,
            self.schemas_dir,
            self.tests_dir,
        ]

        for directory in directories:
            directory.mkdir(
                parents=True,
                exist_ok=True
            )


def build_default_agents() -> Dict[str, AgentConfig]:
    """Create the three independent AI agents."""

    return {
        "chatgpt": AgentConfig(
            name="ChatGPT",
            platform="OpenAI ChatGPT",
            role=AgentRole.CIO,
            responsibilities=(
                "task_planning",
                "research_framework",
                "strategic_analysis",
                "cross_validation",
                "final_decision",
                "report_generation",
            ),
        ),

        "grok": AgentConfig(
            name="Grok",
            platform="xAI Grok",
            role=AgentRole.INTELLIGENCE,
            responsibilities=(
                "market_intelligence",
                "news_monitoring",
                "public_opinion",
                "industry_trends",
                "negative_evidence",
                "counter_arguments",
            ),
        ),

        "hark": AgentConfig(
            name="Hark",
            platform="Hark.com",
            role=AgentRole.ANALYST,
            responsibilities=(
                "independent_research",
                "document_analysis",
                "project_execution",
                "information_organization",
                "research_summaries",
                "workflow_assistance",
            ),
        ),
    }


def get_default_config(
    project_root: Path | str | None = None,
) -> TeamConfig:
    """
    Return the default V3.10 team configuration.

    Default:
        Free manual collaboration
        Investment + General AI projects
        Three independent agents
    """

    if project_root is None:
        root = Path(__file__).resolve().parent.parent
    else:
        root = Path(project_root).expanduser().resolve()

    return TeamConfig(
        project_root=root,
        collaboration_mode=CollaborationMode.FREE_MANUAL,
        project_mode=ProjectMode.BOTH,
        agents=build_default_agents(),
    )


DEFAULT_CONFIG = get_default_config()
