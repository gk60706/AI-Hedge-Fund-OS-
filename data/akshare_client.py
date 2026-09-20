"""V1.4 AkShare 行情接口：A 股代码列表 + 日线行情。"""
import akshare as ak


class AkShareClient:
    """AkShare 数据客户端。"""

    def get_stock_list(self):
        """获取 A 股代码列表。"""
        df = ak.stock_info_a_code_name()
        return df

    def get_daily_price(self, code: str):
        """获取个股前复权日线行情。"""
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            adjust="qfq",
        )
        return df


from pathlib import Path

import pandas as pd


class AkShareClientV36:
    """V3.6 AkShare 数据中心：带本地 CSV 缓存的真实 A 股日线行情。

    第一原则：LLM 永远不能直接“猜”行情，AI 只能消费 Data Center 提供的数据。
    """

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_daily(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        code = code.strip()
        cache_file = self.cache_dir / f"{code}_{start_date}_{end_date}_{adjust}.csv"
        if cache_file.exists():
            df = pd.read_csv(cache_file, parse_dates=["日期"])
            return df
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        except Exception as exc:
            raise RuntimeError(f"AkShare 获取{code}历史数据失败:{exc}") from exc
        if df is None or df.empty:
            raise RuntimeError(f"{code}没有返回历史数据")
        df.to_csv(cache_file, index=False, encoding="utf-8-sig")
        return df


# ============================================================================
# V3.9.1 unified research engine - unified AkShare client
# ============================================================================


class AkShareClientV391:
    """统一行情客户端：带 CSV 缓存 + 归一化。"""

    def __init__(self, cache_dir="data_cache"):
        self.cache = CSVCache(cache_dir)

    def get_daily(self, code: str, start: str = "", end: str = "") -> pd.DataFrame:
        cached = self.cache.get(code)
        if cached is not None and len(cached) > 0:
            return cached
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            adjust="qfq",
            start_date=start or "19900101",
            end_date=end or "20991231",
        )
        df = normalize_daily(df, code)
        self.cache.put(code, df)
        return df
from data.cache import CSVCache
from data.price_loader import normalize_daily


# ============================================================================
# V3.9.2 canonical AkShare client (step3: AkShareConfigV392 + AkShareClientV392)
#
# 设计原则：
#   - 不删除/不覆盖旧版 AkShareClient / AkShareClientV36 / AkShareClientV391
#     （market_service.py / price_loader.py / main_v391.py / tests/test_v36.py /
#      scripts/download_data.py 仍依赖旧版接口）
#   - 新版以 V392 后缀命名，避免命名冲突
#   - 新版输出标准 PanelData（对接 data/schema.py + data/panel.py）
# ============================================================================

import logging as _logging_v392
import time as _time_v392
from dataclasses import dataclass as _dataclass_v392
from pathlib import Path as _PathV392
from typing import (
    Iterable as _IterableV392,
    Optional as _OptionalV392,
    Sequence as _SequenceV392,
)
import numpy as _np_v392
import pandas as _pd_v392

# akshare 已在文件顶部 import 为 ak；V3.9.2 沿用同一别名
from .panel import PanelData, PanelConfig
from .schema import (
    SchemaConfig,
    SchemaError,
    normalize_schema,
    normalize_stock_code,
)

logger = _logging_v392.getLogger("AIHedgeFundOS.AkShareClientV392")


@_dataclass_v392(frozen=True)
class AkShareConfigV392:
    """V3.9.2 AkShare 数据客户端配置。"""

    cache_dir: str = "data/cache/akshare"
    use_cache: bool = True
    force_refresh: bool = False
    max_retries: int = 3
    retry_delay: float = 2.0
    request_interval: float = 0.3
    # "": 不复权 / "qfq": 前复权 / "hfq": 后复权
    adjust: str = "qfq"
    start_date: str = "2010-01-01"
    end_date: str = "2099-12-31"
    calculate_limit_flags: bool = True


class AkShareClientV392:
    """V3.9.2 A 股历史数据客户端。

    示例:
        client = AkShareClientV392()
        df = client.get_daily("600519", "2020-01-01", "2025-01-01")
        panel = client.get_panel(["600519", "000001"],
                                 "2020-01-01", "2025-01-01")
    """

    def __init__(self, config: _OptionalV392[AkShareConfigV392] = None):
        self.config = config or AkShareConfigV392()
        self.cache_dir = _PathV392(self.config.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.last_errors: list = []
        self._check_akshare()

    @staticmethod
    def _check_akshare() -> None:
        if ak is None:
            raise ImportError("未安装 akshare。\n请执行：\npip install akshare")

    @staticmethod
    def _normalize_date(value) -> str:
        date = _pd_v392.Timestamp(value)
        return date.strftime("%Y%m%d")

    @staticmethod
    def _normalize_code(code) -> str:
        code = normalize_stock_code(code)
        if not code:
            raise ValueError("股票代码不能为空")
        return code

    def _cache_path(self, code: str, adjust: _OptionalV392[str] = None) -> _PathV392:
        code = self._normalize_code(code)
        adjust = adjust if adjust is not None else self.config.adjust
        adjust_name = "raw" if adjust == "" else adjust
        return self.cache_dir / f"{code}_{adjust_name}.csv"

    @staticmethod
    def _normalize_akshare_columns(
        df: _pd_v392.DataFrame, code: str
    ) -> _pd_v392.DataFrame:
        """将 AkShare stock_zh_a_hist 中文字段映射为 V3.9.2 标准字段。"""
        if df is None:
            raise SchemaError("AkShare 返回 None")
        if df.empty:
            raise SchemaError(f"{code} AkShare 返回空数据")
        result = df.copy()
        if "股票代码" not in result.columns:
            result["股票代码"] = code
        result = normalize_schema(result, SchemaConfig(strict=True))
        result["code"] = code
        result["available_date"] = result["date"]
        result["is_tradeable"] = True
        result["suspended"] = False
        result["limit_up"] = False
        result["limit_down"] = False
        result["is_st"] = False
        return result

    @staticmethod
    def _limit_ratio(code: str, is_st: bool = False) -> float:
        """粗略 A 股涨跌停比例（研究级近似版）。"""
        code = str(code).zfill(6)
        if is_st:
            return 0.05
        if code.startswith(("300", "301")):
            return 0.20
        if code.startswith(("688", "689")):
            return 0.20
        if code.startswith((
            "430", "831", "832", "833", "834", "835", "836", "837",
            "838", "839", "870", "871", "872", "873", "920",
        )):
            return 0.30
        return 0.10

    @classmethod
    def _calculate_limit_flags(
        cls, df: _pd_v392.DataFrame
    ) -> _pd_v392.DataFrame:
        """根据前收盘价估算涨停/跌停状态（研究级估算）。"""
        result = df.copy()
        result = result.sort_values(["code", "date"])
        result["prev_close"] = result.groupby("code")["close"].shift(1)

        def calc_limit_up(row):
            if _pd_v392.isna(row["prev_close"]) or _pd_v392.isna(row["close"]):
                return False
            ratio = cls._limit_ratio(
                row["code"], bool(row.get("is_st", False))
            )
            theoretical = row["prev_close"] * (1 + ratio)
            theoretical = _np_v392.floor(theoretical * 100 + 0.5) / 100
            return row["close"] >= theoretical - 0.011

        def calc_limit_down(row):
            if _pd_v392.isna(row["prev_close"]) or _pd_v392.isna(row["close"]):
                return False
            ratio = cls._limit_ratio(
                row["code"], bool(row.get("is_st", False))
            )
            theoretical = row["prev_close"] * (1 - ratio)
            theoretical = _np_v392.floor(theoretical * 100 + 0.5) / 100
            return row["close"] <= theoretical + 0.011

        result["limit_up"] = result.apply(calc_limit_up, axis=1)
        result["limit_down"] = result.apply(calc_limit_down, axis=1)
        result = result.drop(columns=["prev_close"])
        return result

    def _download_daily(
        self, code: str, start_date: str, end_date: str, adjust: str
    ) -> _pd_v392.DataFrame:
        """真正调用 AkShare API。"""
        logger.info(
            "Downloading %s: %s -> %s adjust=%s",
            code, start_date, end_date, adjust,
        )
        last_error = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                )
                if df is None:
                    raise RuntimeError("AkShare 返回 None")
                if df.empty:
                    raise RuntimeError(f"{code} 没有返回数据")
                return df
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "AkShare request failed (attempt %s/%s): %s",
                    attempt, self.config.max_retries, exc,
                )
                if attempt < self.config.max_retries:
                    _time_v392.sleep(self.config.retry_delay * attempt)
        raise RuntimeError(f"AkShare 获取 {code} 失败：{last_error}")

    def _load_cache(
        self, code: str, adjust: str
    ) -> _OptionalV392[_pd_v392.DataFrame]:
        path = self._cache_path(code, adjust)
        if not path.exists():
            return None
        try:
            df = _pd_v392.read_csv(path)
            if df.empty:
                return None
            return normalize_schema(df, SchemaConfig(strict=True))
        except Exception as exc:
            logger.warning("读取缓存失败 %s: %s", path, exc)
            return None

    def _save_cache(
        self, code: str, adjust: str, df: _pd_v392.DataFrame
    ) -> _PathV392:
        path = self._cache_path(code, adjust)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path

    def get_daily(
        self,
        code: str,
        start_date=None,
        end_date=None,
        adjust: _OptionalV392[str] = None,
        force_refresh: _OptionalV392[bool] = None,
    ) -> _pd_v392.DataFrame:
        """获取单股票历史日线（标准化 DataFrame）。"""
        code = self._normalize_code(code)
        start = start_date or self.config.start_date
        end = end_date or self.config.end_date
        start_str = self._normalize_date(start)
        end_str = self._normalize_date(end)
        adjust = self.config.adjust if adjust is None else adjust
        force_refresh = (
            self.config.force_refresh if force_refresh is None else force_refresh
        )
        if adjust not in {"", "qfq", "hfq"}:
            raise ValueError("adjust 必须是 '', 'qfq' 或 'hfq'")

        cached = None
        if self.config.use_cache and not force_refresh:
            cached = self._load_cache(code, adjust)
        if cached is not None:
            cached["date"] = _pd_v392.to_datetime(cached["date"])
            mask = (cached["date"] >= _pd_v392.Timestamp(start)) & (
                cached["date"] <= _pd_v392.Timestamp(end)
            )
            result = cached.loc[mask].copy()
            if not result.empty:
                logger.info("Cache hit: %s", code)
                return result.reset_index(drop=True)

        raw = self._download_daily(code, start_str, end_str, adjust)
        result = self._normalize_akshare_columns(raw, code)
        if self.config.calculate_limit_flags:
            result = self._calculate_limit_flags(result)
        if self.config.use_cache:
            try:
                self._save_cache(code, adjust, result)
            except Exception as exc:
                logger.warning("保存缓存失败 %s: %s", code, exc)

        result["date"] = _pd_v392.to_datetime(result["date"])
        mask = (result["date"] >= _pd_v392.Timestamp(start)) & (
            result["date"] <= _pd_v392.Timestamp(end)
        )
        result = result.loc[mask].copy()
        return result.reset_index(drop=True)

    def get_panel(
        self,
        codes: _SequenceV392[str],
        start_date=None,
        end_date=None,
        adjust: _OptionalV392[str] = None,
        force_refresh: _OptionalV392[bool] = None,
        skip_errors: bool = True,
    ) -> PanelData:
        """批量下载多股票历史行情，返回 PanelData。"""
        normalized_codes = [self._normalize_code(c) for c in codes]
        normalized_codes = list(dict.fromkeys(normalized_codes))
        if not normalized_codes:
            raise ValueError("codes 不能为空")

        frames = []
        errors = []
        for index, code in enumerate(normalized_codes, start=1):
            logger.info(
                "Downloading [%s/%s] %s", index, len(normalized_codes), code
            )
            try:
                df = self.get_daily(
                    code=code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                    force_refresh=force_refresh,
                )
                if not df.empty:
                    frames.append(df)
            except Exception as exc:
                errors.append({"code": code, "error": str(exc)})
                logger.error("Failed %s: %s", code, exc)
                if not skip_errors:
                    raise
            if index < len(normalized_codes):
                _time_v392.sleep(self.config.request_interval)

        if not frames:
            raise RuntimeError(
                f"所有股票均未成功获取数据。errors={errors}"
            )
        combined = _pd_v392.concat(frames, ignore_index=True)
        combined = normalize_schema(combined, SchemaConfig(strict=True))
        panel = PanelData(combined, PanelConfig(schema_strict=True))
        self.last_errors = errors
        return panel

    def get_panel_from_file(
        self,
        codes_file: str,
        start_date=None,
        end_date=None,
        adjust: _OptionalV392[str] = None,
        force_refresh: _OptionalV392[bool] = None,
    ) -> PanelData:
        """从文本/CSV 文件读取股票代码，批量下载。"""
        path = _PathV392(codes_file)
        if not path.exists():
            raise FileNotFoundError(f"找不到股票代码文件：{path}")
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = _pd_v392.read_csv(path)
            possible_columns = ["code", "代码", "股票代码", "symbol"]
            code_column = None
            for column in possible_columns:
                if column in df.columns:
                    code_column = column
                    break
            if code_column is None:
                raise ValueError("CSV 中找不到股票代码字段")
            codes = df[code_column].dropna().astype(str).tolist()
        else:
            with open(path, "r", encoding="utf-8") as f:
                codes = [line.strip() for line in f if line.strip()]
        return self.get_panel(
            codes=codes,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            force_refresh=force_refresh,
        )

    def cached_codes(self) -> list:
        """返回当前缓存的股票代码。"""
        result = []
        for path in self.cache_dir.glob("*.csv"):
            name = path.stem
            code = name.split("_")[0]
            if code.isdigit() and len(code) == 6:
                result.append(code)
        return sorted(set(result))

    def clear_cache(
        self,
        code: _OptionalV392[str] = None,
        adjust: _OptionalV392[str] = None,
    ) -> int:
        """删除缓存，返回删除文件数量。"""
        count = 0
        if code is not None:
            code = self._normalize_code(code)
            if adjust is None:
                patterns = [f"{code}_*.csv"]
            else:
                name = "raw" if adjust == "" else adjust
                patterns = [f"{code}_{name}.csv"]
        else:
            patterns = ["*.csv"]
        for pattern in patterns:
            for path in self.cache_dir.glob(pattern):
                try:
                    path.unlink()
                    count += 1
                except Exception as exc:
                    logger.warning("删除缓存失败 %s: %s", path, exc)
        return count

    def cache_info(self) -> dict:
        """获取缓存统计。"""
        files = list(self.cache_dir.glob("*.csv"))
        total_size = sum(
            p.stat().st_size for p in files if p.exists()
        )
        return {
            "cache_dir": str(self.cache_dir),
            "files": len(files),
            "size_mb": round(total_size / 1024 / 1024, 2),
            "codes": len(self.cached_codes()),
        }


def get_a_share_daily(
    code: str,
    start_date=None,
    end_date=None,
    adjust: str = "qfq",
) -> _pd_v392.DataFrame:
    """快速获取单股票行情。"""
    client = AkShareClientV392(AkShareConfigV392(adjust=adjust))
    return client.get_daily(
        code=code, start_date=start_date, end_date=end_date, adjust=adjust
    )


def get_a_share_panel(
    codes: _SequenceV392[str],
    start_date=None,
    end_date=None,
    adjust: str = "qfq",
) -> PanelData:
    """快速获取多股票 Panel。"""
    client = AkShareClientV392(AkShareConfigV392(adjust=adjust))
    return client.get_panel(
        codes=codes, start_date=start_date, end_date=end_date, adjust=adjust
    )
