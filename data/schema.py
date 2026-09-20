"""
AI Hedge Fund OS
V3.9.2
data/schema.py

作用：
1. 定义 V3.9.2 标准化市场数据 Schema
2. 统一不同数据源的字段名称
3. 提供数据类型转换
4. 提供基础数据校验
5. 为 PIT、因子、Alpha、回测提供统一数据协议

核心原则：

    原始数据
        ↓
    Schema 标准化
        ↓
    PanelData
        ↓
    PIT
        ↓
    Factor
        ↓
    Alpha
        ↓
    Backtest

注意：
- available_date 是 PIT 数据防未来函数的核心字段
- signal_date / date 表示数据对应的市场日期
- available_date 表示该数据最早可以被策略知道的日期
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional
import numpy as np
import pandas as pd

# ============================================================
# 1. 标准字段定义
# ============================================================
# 核心市场字段
MARKET_COLUMNS = [
    "date", "code", "open", "high", "low", "close",
    "volume", "amount", "turnover",
]
# 基本面字段
FUNDAMENTAL_COLUMNS = [
    "pe", "pb", "ps", "roe", "roic",
    "revenue_growth", "profit_growth", "market_cap",
]
# PIT / 交易状态字段
PIT_COLUMNS = ["available_date"]
TRADING_COLUMNS = [
    "is_tradeable", "limit_up", "limit_down", "is_st", "suspended",
]
# 可选股票属性
ATTRIBUTE_COLUMNS = ["industry", "ipo_date", "delist_date"]
# 所有标准字段
CANONICAL_COLUMNS = (
    MARKET_COLUMNS + FUNDAMENTAL_COLUMNS + PIT_COLUMNS
    + TRADING_COLUMNS + ATTRIBUTE_COLUMNS
)

# ============================================================
# 2. 必须字段
# ============================================================
REQUIRED_COLUMNS = ["date", "code", "open", "high", "low", "close", "volume"]

# ============================================================
# 3. 常见数据源字段映射
# ============================================================
COLUMN_ALIASES = {
    # 日期
    "日期": "date", "交易日期": "date", "交易日": "date",
    "trade_date": "date", "datetime": "date",
    # 股票代码
    "股票代码": "code", "证券代码": "code", "代码": "code",
    "symbol": "code", "ticker": "code",
    # 价格
    "开盘": "open", "开盘价": "open", "open_price": "open",
    "最高": "high", "最高价": "high", "high_price": "high",
    "最低": "low", "最低价": "low", "low_price": "low",
    "收盘": "close", "收盘价": "close", "close_price": "close",
    # 成交量
    "成交量": "volume", "成交股数": "volume", "volume_shares": "volume",
    # 成交额
    "成交额": "amount", "成交金额": "amount", "turnover_amount": "amount",
    # 换手率
    "换手率": "turnover", "换手": "turnover",
    # 估值
    "市盈率": "pe", "PE": "pe", "pe_ttm": "pe",
    "市净率": "pb", "PB": "pb",
    "市销率": "ps", "PS": "ps",
    # 基本面
    "净资产收益率": "roe", "ROE": "roe",
    "投入资本回报率": "roic", "ROIC": "roic",
    "营业收入增长率": "revenue_growth", "营收增长率": "revenue_growth",
    "revenue_growth_rate": "revenue_growth",
    "净利润增长率": "profit_growth", "利润增长率": "profit_growth",
    "profit_growth_rate": "profit_growth",
    "总市值": "market_cap", "市值": "market_cap", "market_value": "market_cap",
    # PIT
    "数据可用日期": "available_date", "可用日期": "available_date",
    "发布日期": "available_date", "公告日期": "available_date",
    "publish_date": "available_date",
    # 交易状态
    "是否交易": "is_tradeable", "可交易": "is_tradeable", "tradeable": "is_tradeable",
    "涨停": "limit_up", "涨停状态": "limit_up",
    "跌停": "limit_down", "跌停状态": "limit_down",
    "ST": "is_st", "是否ST": "is_st", "is_st_stock": "is_st",
    "停牌": "suspended", "是否停牌": "suspended",
    # 股票属性
    "行业": "industry", "所属行业": "industry",
    "上市日期": "ipo_date", "IPO日期": "ipo_date",
    "退市日期": "delist_date",
}

# ============================================================
# 4. 默认值
# ============================================================
DEFAULT_VALUES = {
    "amount": np.nan, "turnover": np.nan,
    "pe": np.nan, "pb": np.nan, "ps": np.nan,
    "roe": np.nan, "roic": np.nan,
    "revenue_growth": np.nan, "profit_growth": np.nan,
    "market_cap": np.nan,
    "available_date": pd.NaT,
    "is_tradeable": True, "limit_up": False, "limit_down": False,
    "is_st": False, "suspended": False,
    "industry": None, "ipo_date": pd.NaT, "delist_date": pd.NaT,
}

# ============================================================
# 5. Schema 异常
# ============================================================
class SchemaError(ValueError):
    """标准数据 Schema 错误。"""
    pass


# ============================================================
# 6. Schema 配置
# ============================================================
@dataclass(frozen=True)
class SchemaConfig:
    """
    Schema 配置。

    normalize_code:
        是否自动将股票代码标准化为 6 位字符串。

    strict:
        True：缺少 REQUIRED_COLUMNS 直接报错。
        False：仅做尽可能多的标准化。
    """
    normalize_code: bool = True
    strict: bool = True


# ============================================================
# 7. 股票代码标准化
# ============================================================
def normalize_stock_code(code) -> str:
    """
    将股票代码标准化为 6 位字符串。

    示例：
        1       -> 000001
        "1"     -> 000001
        "000001"-> 000001
        600519  -> 600519

    对 ETF / 指数 / 特殊证券：保留原始字符串，但尽可能进行标准化。
    """
    if pd.isna(code):
        return ""
    text = str(code).strip()
    # 处理类似 600519.SH
    if "." in text:
        left, right = text.split(".", 1)
        # 如果已经是数字代码
        if left.isdigit() and len(left) <= 6:
            return left.zfill(6)
    # 处理类似 "SH600519"
    if text.upper().startswith(("SH", "SZ", "BJ")):
        text = text[2:]
    # 纯数字代码
    if text.isdigit():
        return text.zfill(6)
    return text


# ============================================================
# 8. 列名标准化
# ============================================================
def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """将中文字段 / 常见字段映射为标准英文 Schema。"""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df 必须是 pandas.DataFrame")
    result = df.copy()
    rename_map = {}
    for column in result.columns:
        column_str = str(column).strip()
        if column_str in COLUMN_ALIASES:
            rename_map[column] = COLUMN_ALIASES[column_str]
        elif column_str.lower() in COLUMN_ALIASES:
            rename_map[column] = COLUMN_ALIASES[column_str.lower()]
    result = result.rename(columns=rename_map)
    return result


# ============================================================
# 9. 日期标准化
# ============================================================
def normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    """标准化：date / available_date / ipo_date / delist_date"""
    result = df.copy()
    for col in ("date", "available_date", "ipo_date", "delist_date"):
        if col in result.columns:
            result[col] = pd.to_datetime(result[col], errors="coerce").dt.normalize()
    return result


# ============================================================
# 10. 数值字段标准化
# ============================================================
NUMERIC_COLUMNS = [
    "open", "high", "low", "close", "volume", "amount", "turnover",
    "pe", "pb", "ps", "roe", "roic",
    "revenue_growth", "profit_growth", "market_cap",
]


def normalize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    将数值字段统一转换成 float。

    特别处理："12.5%" / "12.5" / "--" / "-" / ""
    """
    result = df.copy()
    for column in NUMERIC_COLUMNS:
        if column not in result.columns:
            continue
        series = result[column]
        # 如果是字符串，处理百分号
        if series.dtype == object:
            series = (
                series.astype(str).str.strip()
                .replace({"--": np.nan, "-": np.nan, "": np.nan,
                          "None": np.nan, "nan": np.nan})
            )
            percentage_mask = series.str.endswith("%", na=False)
            series = series.str.replace("%", "", regex=False)
            numeric = pd.to_numeric(series, errors="coerce")
            # 百分号转换成小数
            numeric.loc[percentage_mask] = numeric.loc[percentage_mask] / 100.0
            result[column] = numeric.astype(float)
        else:
            result[column] = pd.to_numeric(series, errors="coerce").astype(float)
    return result


# ============================================================
# 11. 默认字段补齐
# ============================================================
def add_missing_columns(df: pd.DataFrame) -> pd.DataFrame:
    """为 DataFrame 添加不存在的标准字段。不会覆盖已有字段。"""
    result = df.copy()
    for column in CANONICAL_COLUMNS:
        if column not in result.columns:
            if column in DEFAULT_VALUES:
                result[column] = DEFAULT_VALUES[column]
            else:
                result[column] = np.nan
    return result


# ============================================================
# 12. available_date 默认处理
# ============================================================
def fill_default_available_date(df: pd.DataFrame) -> pd.DataFrame:
    """
    对市场行情字段 date，如果没有明确的 available_date，则：
        available_date = date
    这只适用于日线行情。对财务数据而言，不允许将报告期日期直接当作公告可用日期。
    """
    result = df.copy()
    if "available_date" not in result.columns:
        result["available_date"] = result["date"]
    else:
        result["available_date"] = result["available_date"].fillna(result["date"])
    return result


# ============================================================
# 13. 交易状态标准化
# ============================================================
def normalize_boolean_column(series: pd.Series) -> pd.Series:
    """将常见真假表达转换为 bool。"""
    if series.dtype == bool:
        return series.fillna(False)
    true_values = {True, 1, "1", "true", "True", "TRUE",
                   "是", "Y", "y", "yes", "YES"}
    false_values = {False, 0, "0", "false", "False", "FALSE",
                    "否", "N", "n", "no", "NO"}

    def convert(value):
        if pd.isna(value):
            return False
        if value in true_values:
            return True
        if value in false_values:
            return False
        return bool(value)

    return series.map(convert).astype(bool)


def normalize_trading_status(df: pd.DataFrame) -> pd.DataFrame:
    """标准化交易状态字段。"""
    result = df.copy()
    boolean_columns = ["is_tradeable", "limit_up", "limit_down", "is_st", "suspended"]
    for column in boolean_columns:
        if column in result.columns:
            result[column] = normalize_boolean_column(result[column])
    # 如果明确停牌，则不可交易
    if "suspended" in result.columns:
        result.loc[result["suspended"], "is_tradeable"] = False
    return result


# ============================================================
# 14. 股票代码标准化
# ============================================================
def normalize_codes(df: pd.DataFrame, enabled: bool = True) -> pd.DataFrame:
    """标准化股票代码。"""
    result = df.copy()
    if enabled and "code" in result.columns:
        result["code"] = result["code"].map(normalize_stock_code)
    return result


# ============================================================
# 15. 基础排序
# ============================================================
def sort_panel(df: pd.DataFrame) -> pd.DataFrame:
    """按 date / code 排序。"""
    result = df.copy()
    sort_columns = [c for c in ["date", "code"] if c in result.columns]
    if sort_columns:
        result = result.sort_values(sort_columns, kind="mergesort")
    return result


# ============================================================
# 16. 重复数据处理
# ============================================================
def remove_duplicate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    删除同一 date + code 的重复行情记录。默认保留最后一条。
    注意：如果未来存在多个版本的 PIT 数据，PIT 数据不应简单使用本函数去重。
    """
    result = df.copy()
    if "date" in result.columns and "code" in result.columns:
        result = result.drop_duplicates(subset=["date", "code"], keep="last")
    return result


# ============================================================
# 17. 核心 Schema 校验
# ============================================================
def validate_required_columns(df: pd.DataFrame, strict: bool = True) -> list:
    """检查必须字段。返回缺失字段列表。"""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if strict and missing:
        raise SchemaError("缺少必要字段: " + ", ".join(missing))
    return missing


# ============================================================
# 18. 日期合法性检查
# ============================================================
def validate_dates(df: pd.DataFrame) -> None:
    """检查 date 是否存在非法日期。"""
    if "date" not in df.columns:
        raise SchemaError("缺少 date 字段")
    if df["date"].isna().any():
        count = int(df["date"].isna().sum())
        raise SchemaError(f"存在 {count} 条非法 date 数据")


# ============================================================
# 19. 股票代码合法性检查
# ============================================================
def validate_codes(df: pd.DataFrame) -> None:
    """检查 code 是否为空。"""
    if "code" not in df.columns:
        raise SchemaError("缺少 code 字段")
    empty_mask = df["code"].astype(str).str.strip().eq("")
    if empty_mask.any():
        count = int(empty_mask.sum())
        raise SchemaError(f"存在 {count} 条空股票代码")


# ============================================================
# 20. 价格合法性检查
# ============================================================
def validate_prices(df: pd.DataFrame) -> None:
    """检查 open / high / low / close 是否出现负数或 0。"""
    price_columns = ["open", "high", "low", "close"]
    for column in price_columns:
        if column not in df.columns:
            continue
        invalid = df[column].notna() & (df[column] <= 0)
        if invalid.any():
            count = int(invalid.sum())
            raise SchemaError(f"{column} 存在 {count} 条 \"小于等于 0 的价格\"")


# ============================================================
# 21. OHLC 逻辑检查
# ============================================================
def validate_ohlc(df: pd.DataFrame) -> None:
    """
    检查 OHLC 基础逻辑：
        high >= max(open, close, low)
        low <= min(open, close, high)
    """
    required = ["open", "high", "low", "close"]
    if not all(c in df.columns for c in required):
        return
    valid = df[required].notna().all(axis=1)
    subset = df.loc[valid]
    invalid_high = subset["high"] < subset[["open", "low", "close"]].max(axis=1)
    invalid_low = subset["low"] > subset[["open", "high", "close"]].min(axis=1)
    invalid = invalid_high | invalid_low
    if invalid.any():
        count = int(invalid.sum())
        raise SchemaError(f"发现 {count} 条 OHLC 价格逻辑异常")


# ============================================================
# 22. PIT 核心检查
# ============================================================
def validate_point_in_time(df: pd.DataFrame) -> None:
    """
    检查最核心的 PIT 规则：available_date <= date
    如果 available_date > date，说明该数据在当时尚不可知，属于潜在未来数据 / look-ahead bias。
    """
    if "available_date" not in df.columns or "date" not in df.columns:
        return
    valid = df["available_date"].notna() & df["date"].notna()
    invalid = valid & (df["available_date"] > df["date"])
    if invalid.any():
        count = int(invalid.sum())
        examples = df.loc[invalid, ["date", "code", "available_date"]].head(5).to_dict("records")
        raise SchemaError(
            f"发现 PIT 时间穿越：{count} 条数据的 available_date > date。示例：{examples}"
        )


# ============================================================
# 23. 完整 Schema 标准化
# ============================================================
def normalize_schema(df: pd.DataFrame, config: Optional[SchemaConfig] = None) -> pd.DataFrame:
    """
    V3.9.2 数据进入系统的统一入口。

    流程：原始 DataFrame → 字段映射 → 日期标准化 → 数值标准化 → 股票代码标准化
         → 默认字段补齐 → available_date → 交易状态 → 去重 → 排序 → Schema Validation
    """
    if config is None:
        config = SchemaConfig()
    if not isinstance(df, pd.DataFrame):
        raise TypeError("normalize_schema() 的输入必须是 pandas.DataFrame")
    if df.empty:
        raise SchemaError("输入 DataFrame 为空")
    result = df.copy()
    # Step 1: 字段名称标准化
    result = normalize_column_names(result)
    # Step 2: 日期标准化
    result = normalize_dates(result)
    # Step 3: 数值字段标准化
    result = normalize_numeric_columns(result)
    # Step 4: 股票代码标准化
    result = normalize_codes(result, enabled=config.normalize_code)
    # Step 5: 必须字段检查
    validate_required_columns(result, strict=config.strict)
    # Step 6: 默认字段
    result = add_missing_columns(result)
    # Step 7: PIT 可用日期
    result = fill_default_available_date(result)
    # Step 8: 交易状态
    result = normalize_trading_status(result)
    # Step 9: 去除重复行情
    result = remove_duplicate_rows(result)
    # Step 10: 排序
    result = sort_panel(result)
    # Step 11: 基础验证
    validate_dates(result)
    validate_codes(result)
    validate_prices(result)
    validate_ohlc(result)
    validate_point_in_time(result)
    # Step 12: DataFrame 索引重新整理
    result = result.reset_index(drop=True)
    return result


# ============================================================
# 24-27. 获取标准字段
# ============================================================
def get_canonical_columns() -> list:
    """返回完整标准字段列表。"""
    return list(CANONICAL_COLUMNS)


def get_market_columns() -> list:
    """返回市场行情字段。"""
    return list(MARKET_COLUMNS)


def get_fundamental_columns() -> list:
    """返回基本面字段。"""
    return list(FUNDAMENTAL_COLUMNS)


def get_pit_columns() -> list:
    """返回 PIT 相关字段。"""
    return list(PIT_COLUMNS)


# ============================================================
# 28. 判断是否为 A 股代码
# ============================================================
def is_a_share_code(code: str) -> bool:
    """
    粗略判断是否为沪深北 A 股代码。
    注意：这是研究系统的快速判断，不是交易所官方证券分类器。
    """
    if code is None:
        return False
    code = normalize_stock_code(code)
    if len(code) != 6:
        return False
    prefixes = (
        "000", "001", "002", "003", "300", "301",
        "600", "601", "603", "605", "688", "689",
        "430", "831", "832", "833", "834", "835", "836", "837", "838", "839",
        "870", "871", "872", "873", "920",
    )
    return code.startswith(prefixes)


# ============================================================
# 29. 股票市场分类
# ============================================================
def get_market_type(code: str) -> str:
    """
    根据代码返回粗略市场类型。
    返回：SH_MAIN / SZ_MAIN / SZ_GEM / SH_STAR / BJ / UNKNOWN
    """
    code = normalize_stock_code(code)
    if code.startswith(("600", "601", "603", "605")):
        return "SH_MAIN"
    if code.startswith(("688", "689")):
        return "SH_STAR"
    if code.startswith(("000", "001", "002", "003")):
        return "SZ_MAIN"
    if code.startswith(("300", "301")):
        return "SZ_GEM"
    if code.startswith(("430", "831", "832", "833", "834", "835",
                         "836", "837", "838", "839", "870", "871", "872", "873", "920")):
        return "BJ"
    return "UNKNOWN"


# ============================================================
# 30. Schema 信息
# ============================================================
def schema_summary() -> dict:
    """返回 Schema 描述信息。"""
    return {
        "version": "3.9.2",
        "market_columns": list(MARKET_COLUMNS),
        "fundamental_columns": list(FUNDAMENTAL_COLUMNS),
        "pit_columns": list(PIT_COLUMNS),
        "trading_columns": list(TRADING_COLUMNS),
        "attribute_columns": list(ATTRIBUTE_COLUMNS),
        "required_columns": list(REQUIRED_COLUMNS),
    }


# ============================================================
# 31. 模块测试
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("AI Hedge Fund OS - V3.9.2")
    print("data/schema.py self-test")
    print("=" * 70)
    raw_data = pd.DataFrame({
        "日期": ["2025-01-02", "2025-01-03"],
        "股票代码": ["600519", "600519"],
        "开盘": [1400.0, 1410.0],
        "最高": [1420.0, 1430.0],
        "最低": [1390.0, 1400.0],
        "收盘": [1410.0, 1425.0],
        "成交量": [1000000, 1200000],
        "成交额": [1.4e9, 1.7e9],
        "换手率": [0.5, 0.6],
    })
    normalized = normalize_schema(raw_data)
    print("\n[Schema Summary]")
    print(schema_summary())
    print("\n[Normalized Data]")
    print(normalized)
    print("\n[Market Type]")
    for code in ["600519", "000001", "300750", "688981", "920001"]:
        print(code, "=>", get_market_type(code))
    print("\n[A Share Check]")
    for code in ["600519", "000001", "300750", "688981", "ABC123"]:
        print(code, "=>", is_a_share_code(code))
    print("\nSchema self-test passed.")
