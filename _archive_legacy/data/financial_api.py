"""V0.4 财务数据接口：AkShare 财务指标。"""
from __future__ import annotations

try:
    import akshare as ak
except Exception:  # pragma: no cover
    ak = None


def get_financial_data(code: str) -> dict:
    """获取上市公司财务指标（最新一期 ROE/毛利率/净利率/资产负债率）。"""
    if ak is None:
        return {"roe": None, "gross_margin": None, "net_margin": None, "debt_ratio": None}
    try:
        df = ak.stock_financial_analysis_indicator(symbol=code)
        latest = df.iloc[0]
        return {
            "roe": latest.get("净资产收益率"),
            "gross_margin": latest.get("销售毛利率"),
            "net_margin": latest.get("销售净利率"),
            "debt_ratio": latest.get("资产负债率"),
        }
    except Exception:
        return {"roe": None, "gross_margin": None, "net_margin": None, "debt_ratio": None}
