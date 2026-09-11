"""V2.1 MCP 工具注册：创建默认 server 并注册金融工具。"""

from mcp.server import MCPServer
from mcp.tools import FinancialTools

server = MCPServer()
tools = FinancialTools()

server.register("company_info", tools.company_info)
server.register("news_search", tools.news_search)
