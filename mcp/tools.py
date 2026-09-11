"""V1.1 MCP 工具系统（演示版）。

V2.1 追加：FinancialTools（company_info / news_search）。
"""


class MarketTool:
    name = "market"

    def get_price(self, code):
        return {"code": code, "price": 120}


class NewsTool:
    name = "news"

    def search(self, keyword):
        return ["AI产业增长", "订单增加"]


# ---------------------------------------------------------------------------
# V2.1 金融数据工具：company_info / news_search（研究/模拟占位，不连真实行情）。
# ---------------------------------------------------------------------------
class FinancialTools:
    """V2.1 金融数据工具。"""

    def company_info(self, code):
        """返回公司基本信息（模拟数据）。"""
        return {
            "code": code,
            "industry": "AI产业链",
            "status": "成长",
        }

    def news_search(self, keyword):
        """搜索新闻（模拟数据）。"""
        return [
            {
                "title": f"{keyword} 最新行业动态",
                "sentiment": "positive",
            }
        ]
