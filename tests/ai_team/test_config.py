
from pathlib import Path

from ai_team.config import (
    AgentRole,
    CollaborationMode,
    ProjectMode,
    get_default_config,
)


def test_default_collaboration_mode():
    config = get_default_config()

    assert (
        config.collaboration_mode
        == CollaborationMode.FREE_MANUAL
    )


def test_default_project_mode():
    config = get_default_config()

    assert config.project_mode == ProjectMode.BOTH


def test_three_agents_exist():
    config = get_default_config()

    assert len(config.agents) == 3

    assert "chatgpt" in config.agents
    assert "grok" in config.agents
    assert "hark" in config.agents


def test_agent_roles():
    config = get_default_config()

    assert config.agents["chatgpt"].role == AgentRole.CIO
    assert (
        config.agents["grok"].role
        == AgentRole.INTELLIGENCE
    )
    assert config.agents["hark"].role == AgentRole.ANALYST


def test_free_mode_requires_manual_handoff():
    config = get_default_config()

    assert config.manual_handoff_required is True
    assert config.api_enabled is False


def test_directory_creation(tmp_path: Path):
    config = get_default_config(tmp_path)

    config.create_directories()

    assert config.team_dir.exists()
    assert config.prompts_dir.exists()
    assert config.tasks_dir.exists()
    assert config.reports_dir.exists()
    assert config.evaluation_dir.exists()
    assert config.schemas_dir.exists()
    assert config.tests_dir.exists()


def test_custom_project_root(tmp_path: Path):
    config = get_default_config(tmp_path)

    assert config.project_root == tmp_path.resolve()
