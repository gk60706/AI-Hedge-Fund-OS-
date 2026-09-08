"""V1.1 MCP 统一管理：按名称分发到对应工具。"""
from mcp.tools import (
    MarketTool,
    NewsTool,
)


class MCPServer:
    def __init__(self):
        self.tools = {
            "market": MarketTool(),
            "news": NewsTool(),
        }

    def call(self, tool, params):
        obj = self.tools[tool]
        method = list(params.keys())[0]
        return getattr(obj, method)(params[method])
