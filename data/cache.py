"""V3.0.1 Real Market Data Engine：本地 JSON 缓存。

避免每个 Agent 都重复请求行情。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class DataCache:
    def __init__(
        self,
        directory: str = "data/cache",
        ttl_seconds: int = 60,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.ttl_seconds = ttl_seconds

    def _path(self, key: str) -> Path:
        safe_key = (
            key.replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
        )
        return (
            self.directory
            / f"{safe_key}.json"
        )

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if not path.exists():
            return None
        if (
            time.time()
            - path.stat().st_mtime
            > self.ttl_seconds
        ):
            return None
        try:
            return json.loads(
                path.read_text(encoding="utf-8")
            )
        except Exception:
            return None

    def set(self, key: str, value: dict[str, Any]):
        path = self._path(key)
        path.write_text(
            json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )


# ============================================================================
# V3.9.1 unified research engine - simple CSV cache
# ============================================================================


class CSVCache:
    def __init__(self, cache_dir: str = "data_cache"):
        self.cache_dir = Path(cache_dir)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe}.csv"

    def get(self, key: str):
        path = self._path(key)
        if not path.exists():
            return None
        return pd.read_csv(path, parse_dates=["date"])

    def put(self, key: str, df) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(self._path(key), index=False)
import pandas as pd

# ============================================================================
# V3.9.2 Data Cache Layer (CacheKey / CacheMetadata / CacheStore)
# 来源: ChatGPT「股票分析 - 封装行情采集模块」data/cache.py 完整输出
# 融合规则: 旧版 DataCache/CSVCache 保留; 本段追加; 无符号冲突
# ============================================================================
import hashlib
import json
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

import pandas as pd

# ============================================================
# Constants
# ============================================================
DEFAULT_CACHE_DIR = Path("data/cache")
DEFAULT_FORMAT = "parquet"
SUPPORTED_FORMATS = {"csv", "parquet", "json"}

# ============================================================
# Helpers
# ============================================================
def _normalize_date(value: Any) -> Optional[str]:
    """
    将日期统一转换为 YYYY-MM-DD。

    支持：
    - str
    - datetime
    - date
    - pandas.Timestamp
    """
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return None
    try:
        return pd.to_datetime(text).strftime("%Y-%m-%d")
    except Exception:
        return text


def _normalize_code(code: Any) -> str:
    """
    标准化股票代码。

    示例：
        600519 -> 600519
        SH600519 -> 600519
        sh600519 -> 600519
    """
    value = str(code).strip().upper()
    for prefix in ("SH", "SZ", "BJ", "SS"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value


def _normalize_codes(codes: Optional[Iterable[Any]]) -> list[str]:
    if codes is None:
        return []
    normalized = {
        _normalize_code(code)
        for code in codes
        if code is not None and str(code).strip()
    }
    return sorted(normalized)


def _safe_name(value: Any) -> str:
    """
    将任意字符串转换成适合文件名的形式。
    """
    text = str(value)
    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "_-."
    )
    return "".join(
        char if char in allowed else "_"
        for char in text
    )


# ============================================================
# CacheKey
# ============================================================
@dataclass(frozen=True)
class CacheKey:
    """
    V3.9.2 标准缓存 Key。

    一个缓存对象由以下维度决定：

        dataset
        symbol
        start_date
        end_date
        frequency
        version
        extra

    例如：

        daily_market
        600519
        2020-01-01
        2025-12-31
        1d
        v392
    """
    dataset: str
    symbol: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    frequency: str = "1d"
    version: str = "v392"
    extra: Optional[Mapping[str, Any]] = None

    def normalized(self) -> "CacheKey":
        return CacheKey(
            dataset=str(self.dataset).strip(),
            symbol=(
                _normalize_code(self.symbol)
                if self.symbol
                else None
            ),
            start_date=_normalize_date(self.start_date),
            end_date=_normalize_date(self.end_date),
            frequency=str(self.frequency).strip(),
            version=str(self.version).strip(),
            extra=self.extra,
        )

    def canonical_payload(self) -> dict[str, Any]:
        key = self.normalized()
        extra = dict(key.extra or {})
        return {
            "dataset": key.dataset,
            "symbol": key.symbol,
            "start_date": key.start_date,
            "end_date": key.end_date,
            "frequency": key.frequency,
            "version": key.version,
            "extra": extra,
        }

    def digest(self) -> str:
        """
        生成稳定 SHA256 缓存 Key。
        """
        payload = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()[:20]

    def filename(
        self,
        extension: str = DEFAULT_FORMAT,
    ) -> str:
        extension = extension.lower().lstrip(".")
        if extension not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported cache format: {extension}"
            )
        dataset = _safe_name(self.dataset)
        symbol = (
            _safe_name(self.symbol)
            if self.symbol
            else "ALL"
        )
        start = (
            _safe_name(self.start_date)
            if self.start_date
            else "NA"
        )
        end = (
            _safe_name(self.end_date)
            if self.end_date
            else "NA"
        )
        frequency = _safe_name(self.frequency)
        return (
            f"{dataset}_"
            f"{symbol}_"
            f"{start}_"
            f"{end}_"
            f"{frequency}_"
            f"{self.digest()}"
            f".{extension}"
        )


# ============================================================
# CacheMetadata
# ============================================================
@dataclass
class CacheMetadata:
    """
    缓存元数据。

    用于判断：
    - 数据什么时候抓取
    - 数据覆盖什么日期
    - 数据来自哪个 provider
    - 使用哪个 schema/version
    """
    dataset: str
    created_at: str
    updated_at: str
    row_count: int
    columns: list[str]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    provider: Optional[str] = None
    version: str = "v392"
    checksum: Optional[str] = None
    source: Optional[str] = None
    extra: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "CacheMetadata":
        return cls(
            dataset=data["dataset"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            row_count=int(data.get("row_count", 0)),
            columns=list(data.get("columns", [])),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            provider=data.get("provider"),
            version=data.get("version", "v392"),
            checksum=data.get("checksum"),
            source=data.get("source"),
            extra=data.get("extra"),
        )


# ============================================================
# CacheStore
# ============================================================
class CacheStore:
    """
    V3.9.2 本地缓存管理器。

    示例：

        cache = CacheStore("data/cache")

        key = CacheKey(
            dataset="daily_market",
            symbol="600519",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )

        cache.set(key, df)

        result = cache.get(key)

    默认：
        data/cache/
    """

    def __init__(
        self,
        cache_dir: str | Path = DEFAULT_CACHE_DIR,
        default_format: str = DEFAULT_FORMAT,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.default_format = (
            default_format.lower().lstrip(".")
        )
        if self.default_format not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported cache format: "
                f"{self.default_format}"
            )
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # --------------------------------------------------------
    # Paths
    # --------------------------------------------------------
    def _data_path(
        self,
        key: CacheKey,
        extension: Optional[str] = None,
    ) -> Path:
        extension = (
            extension
            or self.default_format
        )
        return (
            self.cache_dir
            / key.filename(extension)
        )

    def _metadata_path(
        self,
        data_path: Path,
    ) -> Path:
        return data_path.with_suffix(
            data_path.suffix
            + ".meta.json"
        )

    # --------------------------------------------------------
    # Exists
    # --------------------------------------------------------
    def exists(
        self,
        key: CacheKey,
        *,
        extension: Optional[str] = None,
    ) -> bool:
        """
        判断缓存是否存在。
        """
        path = self._data_path(
            key,
            extension,
        )
        return path.exists()

    # --------------------------------------------------------
    # Expiration
    # --------------------------------------------------------
    def is_expired(
        self,
        key: CacheKey,
        *,
        ttl_seconds: Optional[int] = None,
        extension: Optional[str] = None,
    ) -> bool:
        """
        判断缓存是否过期。

        ttl_seconds=None：
            使用 CacheStore 默认 TTL。

        如果没有设置 TTL：
            永不过期。
        """
        path = self._data_path(
            key,
            extension,
        )
        if not path.exists():
            return True
        ttl = (
            ttl_seconds
            if ttl_seconds is not None
            else self.ttl_seconds
        )
        if ttl is None:
            return False
        age = time.time() - path.stat().st_mtime
        return age > ttl

    # --------------------------------------------------------
    # Read
    # --------------------------------------------------------
    def get(
        self,
        key: CacheKey,
        *,
        allow_expired: bool = False,
        extension: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        读取缓存。

        返回：
            DataFrame
            或 None
        """
        path = self._data_path(
            key,
            extension,
        )
        if not path.exists():
            return None
        if (
            not allow_expired
            and self.is_expired(
                key,
                extension=extension,
            )
        ):
            return None
        try:
            return self._read_dataframe(
                path
            )
        except Exception:
            # 缓存损坏时不应该阻塞主数据流程
            return None

    # --------------------------------------------------------
    # Read metadata
    # --------------------------------------------------------
    def get_metadata(
        self,
        key: CacheKey,
        *,
        extension: Optional[str] = None,
    ) -> Optional[CacheMetadata]:
        path = self._data_path(
            key,
            extension,
        )
        metadata_path = self._metadata_path(
            path
        )
        if not metadata_path.exists():
            return None
        try:
            with metadata_path.open(
                "r",
                encoding="utf-8",
            ) as f:
                payload = json.load(f)
            return CacheMetadata.from_dict(
                payload
            )
        except Exception:
            return None

    # --------------------------------------------------------
    # Write
    # --------------------------------------------------------
    def set(
        self,
        key: CacheKey,
        df: pd.DataFrame,
        *,
        provider: Optional[str] = None,
        source: Optional[str] = None,
        extra_metadata: Optional[
            Mapping[str, Any]
        ] = None,
        extension: Optional[str] = None,
    ) -> Path:
        """
        写入 DataFrame 缓存。

        使用临时文件 + replace，避免程序中断
        导致缓存文件半写入。
        """
        if not isinstance(
            df,
            pd.DataFrame,
        ):
            raise TypeError(
                "CacheStore.set() requires "
                "a pandas DataFrame."
            )
        extension = (
            extension
            or self.default_format
        ).lower().lstrip(".")
        if extension not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported cache format: "
                f"{extension}"
            )
        path = self._data_path(
            key,
            extension,
        )
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._atomic_write_dataframe(
            df,
            path,
        )
        metadata = self._build_metadata(
            key,
            df,
            provider=provider,
            source=source,
            extra_metadata=extra_metadata,
        )
        metadata_path = self._metadata_path(
            path
        )
        self._atomic_write_json(
            metadata.to_dict(),
            metadata_path,
        )
        return path

    # --------------------------------------------------------
    # Delete
    # --------------------------------------------------------
    def delete(
        self,
        key: CacheKey,
        *,
        extension: Optional[str] = None,
    ) -> bool:
        """
        删除指定缓存。

        返回：
            True  -> 删除成功
            False -> 缓存不存在
        """
        path = self._data_path(
            key,
            extension,
        )
        metadata_path = self._metadata_path(
            path
        )
        existed = path.exists()
        if path.exists():
            path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()
        return existed

    # --------------------------------------------------------
    # Clear
    # --------------------------------------------------------
    def clear(
        self,
        *,
        dataset: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> int:
        """
        清理缓存。

        可以按：
        - dataset
        - symbol

        进行过滤。

        返回删除文件数量。
        """
        removed = 0
        for path in self.cache_dir.iterdir():
            if not path.is_file():
                continue
            if path.name.endswith(".meta.json"):
                continue
            if dataset:
                dataset_name = _safe_name(
                    dataset
                )
                if not path.name.startswith(
                    dataset_name + "_"
                ):
                    continue
            if symbol:
                normalized_symbol = _normalize_code(
                    symbol
                )
                if (
                    f"_{normalized_symbol}_"
                    not in path.name
                ):
                    continue
            try:
                path.unlink()
                removed += 1
                metadata_path = (
                    self._metadata_path(
                        path
                    )
                )
                if metadata_path.exists():
                    metadata_path.unlink()
            except OSError:
                continue
        return removed

    # --------------------------------------------------------
    # List
    # --------------------------------------------------------
    def list_cache(
        self,
        *,
        dataset: Optional[str] = None,
    ) -> list[Path]:
        """
        获取缓存文件列表。
        """
        files = []
        for path in self.cache_dir.iterdir():
            if not path.is_file():
                continue
            if path.name.endswith(".meta.json"):
                continue
            if dataset:
                dataset_name = _safe_name(
                    dataset
                )
                if not path.name.startswith(
                    dataset_name + "_"
                ):
                    continue
            files.append(path)
        return sorted(files)

    # --------------------------------------------------------
    # Save JSON
    # --------------------------------------------------------
    def set_json(
        self,
        key: CacheKey,
        payload: Any,
    ) -> Path:
        """
        保存任意 JSON 数据。

        主要用于：
        - universe metadata
        - API response metadata
        - experiment metadata
        """
        path = self._data_path(
            key,
            "json",
        )
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._atomic_write_json(
            payload,
            path,
        )
        return path

    # --------------------------------------------------------
    # Get JSON
    # --------------------------------------------------------
    def get_json(
        self,
        key: CacheKey,
        *,
        allow_expired: bool = False,
    ) -> Optional[Any]:
        path = self._data_path(
            key,
            "json",
        )
        if not path.exists():
            return None
        if (
            not allow_expired
            and self.is_expired(
                key,
                extension="json",
            )
        ):
            return None
        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as f:
                return json.load(f)
        except Exception:
            return None

    # ========================================================
    # Internal
    # ========================================================
    def _read_dataframe(
        self,
        path: Path,
    ) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path)
        if suffix == ".parquet":
            return pd.read_parquet(path)
        if suffix == ".json":
            return pd.read_json(path)
        raise ValueError(
            f"Unsupported cache file: "
            f"{path}"
        )

    def _atomic_write_dataframe(
        self,
        df: pd.DataFrame,
        path: Path,
    ) -> None:
        """
        原子写入 DataFrame。
        """
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        fd, temp_name = tempfile.mkstemp(
            prefix=".cache_",
            suffix=path.suffix,
            dir=str(path.parent),
        )
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            if path.suffix == ".csv":
                df.to_csv(
                    temp_path,
                    index=False,
                    encoding="utf-8-sig",
                )
            elif path.suffix == ".parquet":
                df.to_parquet(
                    temp_path,
                    index=False,
                )
            elif path.suffix == ".json":
                df.to_json(
                    temp_path,
                    orient="records",
                    force_ascii=False,
                    date_format="iso",
                )
            else:
                raise ValueError(
                    f"Unsupported cache format: "
                    f"{path.suffix}"
                )
            temp_path.replace(path)
        finally:
            if temp_path.exists():
                temp_path.unlink(
                    missing_ok=True
                )

    def _atomic_write_json(
        self,
        payload: Any,
        path: Path,
    ) -> None:
        """
        原子写入 JSON。
        """
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        fd, temp_name = tempfile.mkstemp(
            prefix=".metadata_",
            suffix=".json",
            dir=str(path.parent),
        )
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            with temp_path.open(
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    payload,
                    f,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            temp_path.replace(path)
        finally:
            if temp_path.exists():
                temp_path.unlink(
                    missing_ok=True
                )

    def _build_metadata(
        self,
        key: CacheKey,
        df: pd.DataFrame,
        *,
        provider: Optional[str],
        source: Optional[str],
        extra_metadata: Optional[
            Mapping[str, Any]
        ],
    ) -> CacheMetadata:
        now = datetime.now().isoformat(
            timespec="seconds"
        )
        start_date = _normalize_date(
            key.start_date
        )
        end_date = _normalize_date(
            key.end_date
        )
        # 如果 Key 没有提供日期，
        # 尝试从 DataFrame 的 date 列推断。
        if "date" in df.columns:
            dates = pd.to_datetime(
                df["date"],
                errors="coerce",
            ).dropna()
            if not dates.empty:
                if start_date is None:
                    start_date = dates.min().strftime(
                        "%Y-%m-%d"
                    )
                if end_date is None:
                    end_date = dates.max().strftime(
                        "%Y-%m-%d"
                    )
        checksum = self._dataframe_checksum(
            df
        )
        return CacheMetadata(
            dataset=key.dataset,
            created_at=now,
            updated_at=now,
            row_count=len(df),
            columns=[
                str(column)
                for column in df.columns
            ],
            start_date=start_date,
            end_date=end_date,
            provider=provider,
            version=key.version,
            checksum=checksum,
            source=source,
            extra=dict(
                extra_metadata
                or {}
            ),
        )

    @staticmethod
    def _dataframe_checksum(
        df: pd.DataFrame,
    ) -> str:
        """
        对 DataFrame 生成轻量 checksum。

        用于检测缓存内容是否发生变化。
        """
        if df.empty:
            payload = b"EMPTY_DATAFRAME"
        else:
            normalized = df.copy()
            # 保证 column 顺序稳定
            normalized = normalized.reindex(
                sorted(
                    normalized.columns
                ),
                axis=1,
            )
            try:
                hashed = pd.util.hash_pandas_object(
                    normalized,
                    index=True,
                )
                payload = hashed.values.tobytes()
            except Exception:
                payload = repr(
                    normalized.to_dict()
                ).encode("utf-8")
        return hashlib.sha256(
            payload
        ).hexdigest()


# ============================================================
# Convenience Functions
# ============================================================
def make_cache_key(
    dataset: str,
    *,
    symbol: Optional[str] = None,
    start_date: Optional[Any] = None,
    end_date: Optional[Any] = None,
    frequency: str = "1d",
    version: str = "v392",
    extra: Optional[
        Mapping[str, Any]
    ] = None,
) -> CacheKey:
    """
    快捷创建 CacheKey。
    """
    return CacheKey(
        dataset=dataset,
        symbol=symbol,
        start_date=_normalize_date(
            start_date
        ),
        end_date=_normalize_date(
            end_date
        ),
        frequency=frequency,
        version=version,
        extra=extra,
    ).normalized()


def get_default_cache(
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
) -> CacheStore:
    """
    获取默认 CacheStore。
    """
    return CacheStore(
        cache_dir=cache_dir
    )


# ============================================================
# Legacy-compatible helpers
# ============================================================
def cache_exists(
    cache_dir: str | Path,
    key: CacheKey,
) -> bool:
    """
    兼容旧代码的快捷接口。
    """
    return CacheStore(
        cache_dir
    ).exists(key)


def load_cache(
    cache_dir: str | Path,
    key: CacheKey,
    *,
    allow_expired: bool = False,
) -> Optional[pd.DataFrame]:
    """
    兼容旧代码的缓存读取接口。
    """
    return CacheStore(
        cache_dir
    ).get(
        key,
        allow_expired=allow_expired,
    )


def save_cache(
    cache_dir: str | Path,
    key: CacheKey,
    df: pd.DataFrame,
    *,
    provider: Optional[str] = None,
    source: Optional[str] = None,
) -> Path:
    """
    兼容旧代码的缓存保存接口。
    """
    return CacheStore(
        cache_dir
    ).set(
        key,
        df,
        provider=provider,
        source=source,
    )


# ============================================================
# Module exports
# ============================================================
__all__ = [
    "CacheKey",
    "CacheMetadata",
    "CacheStore",
    "DEFAULT_CACHE_DIR",
    "DEFAULT_FORMAT",
    "SUPPORTED_FORMATS",
    "make_cache_key",
    "get_default_cache",
    "cache_exists",
    "load_cache",
    "save_cache",
]
