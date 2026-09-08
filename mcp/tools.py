"""V1.1 MCP 工具系统（演示版）。"""


class MarketTool:
    name = "market"

    def get_price(self, code):
        return {"code": code, "price": 120}


class NewsTool:
    name = "news"

    def search(self, keyword):
        return ["AI产业增长", "订单增加"]
