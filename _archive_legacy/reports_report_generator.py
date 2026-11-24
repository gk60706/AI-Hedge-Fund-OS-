"""V0.4 AI 投资报告生成。"""
from __future__ import annotations

from datetime import datetime


def generate_report(stock: str, result: dict) -> str:
    content = f"""
# AI Hedge Fund OS 投资研究报告

股票: {stock}
生成时间: {datetime.now()}
## 基本面评分
{result["fundamental_score"]}
## Agent分析

"""
    for a in result["agents"]:
        content += f"""
### {a.agent}
评分: {a.score}
观点: {a.opinion}
风险: {a.risks}
"""
    return content


# ---------------------------------------------------------------------------
# V2.0 投资报告生成器（多智能体基金经理系统）：AI 基金晨报。
# 与 V0.4 generate_report 函数并存，不删除已有功能。
# ---------------------------------------------------------------------------
class ReportGenerator:
    """V2.0 根据基金状态生成晨报文本。"""

    def generate(self, state: dict) -> str:
        """Args:
            state: 含 stock_code / research_report / quant_signal /
                   macro_view / final_decision 的状态字典。

        Returns:
            AI 基金晨报文本。
        """
        return f"""
AI基金晨报


股票: {state['stock_code']}
研究: {state['research_report']}
量化: {state['quant_signal']}
宏观: {state['macro_view']}
最终: {state['final_decision']}
"""
