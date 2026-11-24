"""V1.4 5000 股票扫描器：用投资经理团队对每只股票求平均分。

V2.2 追加：StockScannerV22（A股股票扫描 Agent，动量/量能/资金流因子打分）。
"""


class StockScanner:
    """股票扫描器：聚合多个投资经理的分析分数。"""

    def __init__(self, agents: list) -> None:
        self.agents = agents

    def scan(self, stocks: list) -> list:
        results = []
        for stock in stocks:
            score = 0
            for agent in self.agents:
                result = agent.analyze(stock)
                score += result["score"]
            if self.agents:
                score /= len(self.agents)
            results.append(
                {
                    "code": stock["code"],
                    "score": score,
                }
            )
        return sorted(results, key=lambda x: x["score"], reverse=True)


# ---------------------------------------------------------------------------
# V2.2 A股股票扫描 Agent：扫描 5000 只股票寻找强趋势、资金流入、AI 热点。
# ---------------------------------------------------------------------------
class StockScannerV22:
    """V2.2 因子扫描器：按动量/量能/资金流打分（>=70 入选）。"""

    def __init__(self, market_data):
        self.data = market_data

    def scan(self) -> list:
        """扫描并返回按分数降序的候选股列表。

        Returns:
            [{"code": str, "score": int}, ...]
        """
        candidates = []
        for stock in self.data:
            score = 0
            if stock["momentum"] > 0:
                score += 30
            if stock["volume_ratio"] > 1.5:
                score += 30
            if stock["fund_flow"] > 0:
                score += 40
            if score >= 70:
                candidates.append(
                    {
                        "code": stock["code"],
                        "score": score,
                    }
                )
        return sorted(candidates, key=lambda x: x["score"], reverse=True)

# ============================================================
# V3.0 AI Autonomous Hedge Fund：股票池扫描器
# ============================================================
class StockScannerV30:
    def __init__(
        self,
        min_market_cap: float = 5e9,
        max_pe: float = 100,
        min_turnover: float = 0.5,
    ):
        self.min_market_cap = min_market_cap
        self.max_pe = max_pe
        self.min_turnover = min_turnover

    def filter_stock(
        self,
        stock: dict,
    ) -> bool:
        market_cap = stock.get("market_cap")
        pe = stock.get("pe_dynamic")
        turnover = stock.get("turnover_pct")
        if market_cap is not None:
            if market_cap < self.min_market_cap:
                return False
        if pe is not None:
            if pe <= 0 or pe > self.max_pe:
                return False
        if turnover is not None:
            if turnover < self.min_turnover:
                return False
        return True

    def scan(
        self,
        stocks: list,
        limit: int = 100,
    ) -> list:
        candidates = []
        for stock in stocks:
            if self.filter_stock(stock):
                candidates.append(stock)
        candidates.sort(
            key=lambda x: (
                x.get("change_pct") or 0
            ),
            reverse=True,
        )
        return candidates[:limit]

# ============================================================
# V3.0.2 5000 A 股自动扫描：DataFrame 批量扫描
# ============================================================
from scanner.universe import AShareUniverse


class StockScannerV302:
    def __init__(
        self,
        min_market_cap: float = 5e9,
        max_pe: float = 120,
        min_turnover: float = 0.5,
    ):
        self.min_market_cap = min_market_cap
        self.max_pe = max_pe
        self.min_turnover = min_turnover
        self.universe = AShareUniverse()

    def scan_dataframe(
        self,
        df,
        limit: int = 100,
    ) -> list:
        data = self.universe.clean(df)
        # 市值过滤
        if "总市值" in data.columns:
            data = data[
                data["总市值"].fillna(0) >= self.min_market_cap
            ]
        # PE过滤
        if "市盈率-动态" in data.columns:
            pe = data["市盈率-动态"]
            data = data[
                pe.isna()
                | ((pe > 0) & (pe <= self.max_pe))
            ]
        # 换手率
        if "换手率" in data.columns:
            data = data[
                data["换手率"].fillna(0) >= self.min_turnover
            ]
        # 按涨跌幅进行第一轮排序
        if "涨跌幅" in data.columns:
            data = data.sort_values(
                "涨跌幅",
                ascending=False,
            )
        data = data.head(limit)
        result = []
        for _, row in data.iterrows():
            result.append({
                "code": str(row["代码"]).zfill(6),
                "name": str(row["名称"]),
                "latest_price": row.get("最新价"),
                "change_pct": row.get("涨跌幅"),
                "turnover_pct": row.get("换手率"),
                "pe_dynamic": row.get("市盈率-动态"),
                "pb": row.get("市净率"),
                "market_cap": row.get("总市值"),
            })
        return result
