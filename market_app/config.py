from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "A股趋势工作台"
APP_NAME_EN = "AStockWorkbench"
VERSION = "1.1.0"


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


if _is_frozen():
    # exe 同级目录用于放缓存、自选和日志；只读资源在 _MEIPASS。
    APP_HOME = Path(sys.executable).resolve().parent
    RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", APP_HOME))
else:
    APP_HOME = Path(__file__).resolve().parents[1]
    RESOURCE_ROOT = APP_HOME

STATIC_DIR = RESOURCE_ROOT / "market_app" / "static"
DATA_DIR = Path(os.environ.get("ASTOCK_DATA_DIR", APP_HOME / "market_data")).resolve()
CACHE_DIR = DATA_DIR / "cache"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"
SCREEN_CACHE_DIR = CACHE_DIR / "tencent"

for _directory in (DATA_DIR, CACHE_DIR, SCREEN_CACHE_DIR):
    _directory.mkdir(parents=True, exist_ok=True)
