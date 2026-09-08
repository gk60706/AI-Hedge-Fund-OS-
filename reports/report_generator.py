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
