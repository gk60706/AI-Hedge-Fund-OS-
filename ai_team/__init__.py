
"""
AI Hedge Fund OS - Multi-AI Team Package (V3.10)

顶层保持轻量：只直接导入配置层对象，其余公开接口按需惰性加载，
避免 ``ai_team.research_pipeline`` 反向导入本包时产生循环依赖。
"""

from ai_team.config import (
    AgentConfig,
    AgentRole,
    CollaborationMode,
    ProjectMode,
    TeamConfig,
    build_default_agents,
    get_default_config,
)

__version__ = "3.10.0"

# name -> (module, attribute)
_LAZY_EXPORTS = {
    # 任务与报告
    "TaskManager": ("ai_team.task_manager", "TaskManager"),
    "ReportCollector": ("ai_team.report_collector", "ReportCollector"),
    "CrossValidator": ("ai_team.cross_validator", "CrossValidator"),
    "validate_evidence_contract": (
        "ai_team.evidence_contract",
        "validate_evidence_contract",
    ),
    # 辩论与共识
    "DebateEngine": ("ai_team.debate_engine", "DebateEngine"),
    "DebatePosition": ("ai_team.debate_engine", "DebatePosition"),
    "DebateConclusion": ("ai_team.debate_engine", "DebateConclusion"),
    "ConsensusEngine": ("ai_team.consensus_engine", "ConsensusEngine"),
    # 投委会
    "InvestmentCommittee": ("ai_team.investment_committee", "InvestmentCommittee"),
    # 端到端入口
    "V310ResearchPipeline": ("ai_team.research_pipeline", "V310ResearchPipeline"),
    "AgentReport": ("ai_team.research_pipeline", "AgentReport"),
    "DebateContribution": ("ai_team.research_pipeline", "DebateContribution"),
    "RetryPolicy": ("ai_team.research_pipeline", "RetryPolicy"),
    "ResearchOutcome": ("ai_team.research_pipeline", "ResearchOutcome"),
    "AgentTimeoutError": ("ai_team.research_pipeline", "AgentTimeoutError"),
    "HardTimeoutNotSupportedError": (
        "ai_team.research_pipeline",
        "HardTimeoutNotSupportedError",
    ),
    "InsufficientAgentsError": (
        "ai_team.research_pipeline",
        "InsufficientAgentsError",
    ),
    # 真实 API 适配器
    "AdapterRegistry": ("ai_team.adapters", "AdapterRegistry"),
    "OpenAICompatibleAdapter": ("ai_team.adapters", "OpenAICompatibleAdapter"),
    "build_registry": ("ai_team.adapters", "build_registry"),
    "generate_reports": ("ai_team.adapters", "generate_reports"),
    "AdapterError": ("ai_team.adapters", "AdapterError"),
    "AdapterConfigError": ("ai_team.adapters", "AdapterConfigError"),
    "AdapterUnavailableError": ("ai_team.adapters", "AdapterUnavailableError"),
    "AdapterResponseError": ("ai_team.adapters", "AdapterResponseError"),
    "AdapterRateLimitError": ("ai_team.adapters", "AdapterRateLimitError"),
    # 自定义多 provider 配置
    "ProviderConfig": ("ai_team.providers", "ProviderConfig"),
    "load_providers": ("ai_team.providers", "load_providers"),
    "build_custom_registry": ("ai_team.providers", "build_custom_registry"),
    "describe_providers": ("ai_team.providers", "describe_providers"),
}

__all__ = [
    "AgentConfig",
    "AgentRole",
    "CollaborationMode",
    "ProjectMode",
    "TeamConfig",
    "build_default_agents",
    "get_default_config",
    *sorted(_LAZY_EXPORTS),
]


def __getattr__(name: str):
    """按需加载公开接口（PEP 562）。"""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    module = import_module(target[0])
    value = getattr(module, target[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
