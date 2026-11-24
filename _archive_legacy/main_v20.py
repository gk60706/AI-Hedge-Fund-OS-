"""AI Hedge Fund OS V2.0 主程序：多智能体 AI 基金经理演示。

研究/模拟用途，不连接任何实盘交易接口。
"""

from agents.research_agent import ResearchAgent
from agents.quant_agent import QuantAgentV20
from agents.cio_agent import CIOAgent

state = {
    "stock_code": "300394",
    "research_report": "优秀成长公司",
    "quant_signal": "BUY",
    "macro_view": "中性",
}

cio = CIOAgent()
decision = cio.decide(state)
print("AI基金委员会决定:")
print(decision)
