"""V0.3 股票池扫描器：A 股全市场池 + 流动性过滤。"""
from __future__ import annotations

import pandas as pd

try:
    import akshare as ak
except Exception:  # pragma: no cover - akshare 未安装时保持模块可导入
    ak = None

_POOL_COLUMNS = ["代码", "名称", "最新价", "涨跌幅", "成交额", "换手率"]


def get_all_stock_pool() -> pd.DataFrame:
    """获取 A 股股票池：过滤 ST、过滤停牌。"""
    if ak is None:
        return pd.DataFrame(columns=_POOL_COLUMNS)
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception:
        # 东财 WAF 限流等异常时返回空池，由调用方提示稍后重试
        return pd.DataFrame(columns=_POOL_COLUMNS)
    # 删除 ST
    df = df[~df["名称"].str.contains("ST", na=False)]
    # 删除停牌
    df = df[df["最新价"] > 0]
    return df


def filter_liquidity(df: pd.DataFrame, min_amount: float = 50_000_000) -> pd.DataFrame:
    """成交额过滤（默认 ≥5000 万元）。"""
    return df[df["成交额"] >= min_amount]


def create_stock_pool() -> pd.DataFrame:
    df = get_all_stock_pool()
    df = filter_liquidity(df)
    if df.empty:
        return pd.DataFrame(columns=_POOL_COLUMNS)
    return df[_POOL_COLUMNS]
