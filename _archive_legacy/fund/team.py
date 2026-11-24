"""V1.3 多 Agent 基金经理组合：组建 AI 基金投资团队。"""

from agents.quant_agent import QuantAgent
from agents.trend_agent import TrendAgent
from agents.value_agent import ValueAgent


def create_team() -> list:
    """创建默认 AI 基金投资团队（价值/趋势/量化）。"""
    return [
        ValueAgent("价值投资经理"),
        TrendAgent("趋势交易经理"),
        QuantAgent("量化基金经理"),
    ]
