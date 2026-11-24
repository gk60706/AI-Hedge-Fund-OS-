"""V2.1 运行入口：CIO 通过 MCP 工具研究并决策（演示）。"""

from mcp.register import server
from agents.cio_v21 import CIOAgentV21

cio = CIOAgentV21()
result = cio.research("300394", server)
decision = cio.decide(result)
print(result)
print("AI CIO决定:", decision)
