"""V2.1 CIO Agent（升级版）：通过 MCP 工具完成研究与决策。"""


class CIOAgentV21:
    """V2.1 CIO：调用全部工具做研究，再给出投资决定。"""

    def research(self, stock: str, tools):
        """通过 MCP 工具获取公司信息与新闻。

        Args:
            stock: 股票代码。
            tools: MCPServer 实例。

        Returns:
            {"company": ..., "news": [...]}
        """
        company = tools.call("company_info", {"code": stock})
        news = tools.call("news_search", {"keyword": stock})
        return {"company": company, "news": news}

    def decide(self, research: dict) -> str:
        """基于研究结果决策。

        Args:
            research: research() 的返回。

        Returns:
            "BUY_WATCH" 或 "HOLD"。
        """
        if len(research["news"]) > 0:
            return "BUY_WATCH"
        return "HOLD"
