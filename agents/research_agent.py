"""V0.2 Research Agent：基本面研究。"""
from __future__ import annotations

from agents.models import AgentResult


def research_agent(stock: dict) -> AgentResult:
    score = 60
    risks: list[str] = []
    turnover = stock.get("turnover") or 0
    if turnover > 15:
        risks.append("换手率过高")
        score -= 10
    return AgentResult(
        agent="Research",
        score=score,
        opinion="基础面数据待接入财报系统",
        risks=risks,
    )


# ---------------------------------------------------------------------------
# V2.0 研究员 Agent（多智能体基金经理系统）：分析公司基本面/财报/行业周期/
# 竞争优势。与上方 V0.2 的 research_agent 函数并存，不删除已有功能。
# ---------------------------------------------------------------------------
class ResearchAgent:
    """V2.0 基本面研究员（研究/模拟用途）。"""

    def analyze(self, stock: str) -> str:
        """输出基本面分析报告。

        Args:
            stock: 股票代码。

        Returns:
            基本面分析文本。
        """
        report = f"""
股票: {stock}
基本面分析:

1. 收入增长

2. 盈利能力

3. 行业竞争


投资评级:

BUY WATCH

"""
        return report
