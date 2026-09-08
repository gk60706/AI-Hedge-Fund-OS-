"""V1.0 MCP 行情工具（演示版）。"""


class MarketTool:
    name = "market_data"

    def get_price(self, code):
        return {"code": code, "price": 100}
