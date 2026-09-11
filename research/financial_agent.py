"""V2.1 金融数据 Agent：行情/基本面数据服务（研究/模拟占位）。"""


class FinancialAgent:
    """金融数据 Agent。"""

    def quote(self, code: str) -> dict:
        """获取行情快照（模拟数据）。"""
        return {"code": code, "price": 0.0, "change_pct": 0.0}

    def fundamentals(self, code: str) -> dict:
        """获取基本面摘要（模拟数据）。"""
        return {"code": code, "revenue_growth": 0.0, "profit_margin": 0.0}
