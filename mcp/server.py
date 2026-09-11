"""V1.1 MCP 统一管理：按名称分发到对应工具。

V2.1 增强：新增 register() 注册机制（Agent 不直接写死功能，而是调用工具），
call() 优先走注册表；未注册名称仍走 V1.1 的 MarketTool/NewsTool 路径，
保留已有功能。
"""
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
        self._registry = {}

    def call(self, tool, params):
        if tool in self._registry:
            return self._registry[tool](**params)
        obj = self.tools[tool]
        method = list(params.keys())[0]
        return getattr(obj, method)(params[method])

    def register(self, name: str, func) -> None:
        """V2.1：注册一个可调用工具。"""
        self._registry[name] = func
