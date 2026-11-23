from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from datetime import timedelta
from typing import Any

from . import data_sources as ds
from .config import DATA_DIR

LEDGER_PATH = DATA_DIR / "signal_ledger.sqlite"
_lock = threading.RLock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(LEDGER_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            quality_score REAL,
            grade TEXT,
            signal_status TEXT,
            fresh_signal INTEGER,
            top_rank INTEGER,
            trend_score REAL,
            payload TEXT,
            recorded_at TEXT NOT NULL,
            UNIQUE(trade_date, symbol)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_signals_trade_date ON signals(trade_date)"
    )
    return conn


def record_top_picks(result: dict[str, Any], universe: str = "") -> int:
    """把一次选股的 Top K 快照写入台账，同一天同一只股票只记一次。"""
    picks = result.get("top_picks") or []
    if not picks:
        return 0
    inserted = 0
    recorded_at = ds.now_text()
    with _lock, closing(_connect()) as conn:
        with conn:
            for rank, item in enumerate(picks, start=1):
                trade_date = str(item.get("as_of") or "").strip()
                symbol = str(item.get("symbol") or "").strip()
                if not trade_date or not symbol:
                    continue
                quality = item.get("quality") or {}
                payload = {
                    "universe": universe,
                    "daily_top_k": result.get("daily_top_k"),
                    "conditions": result.get("conditions"),
                    "match_mode": result.get("match_mode"),
                    "metrics": quality.get("metrics"),
                    "warnings": quality.get("warnings"),
                    "matched": item.get("matched"),
                    "data_note": item.get("data_note"),
                }
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO signals
                    (trade_date, symbol, name, quality_score, grade, signal_status,
                     fresh_signal, top_rank, trend_score, payload, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trade_date,
                        symbol,
                        item.get("name") or symbol,
                        float(item.get("quality_score") or 0),
                        str(quality.get("grade") or ""),
                        str(item.get("signal_status") or ""),
                        1 if item.get("fresh_signal") else 0,
                        rank,
                        float(item.get("score") or 0),
                        json.dumps(payload, ensure_ascii=False),
                        recorded_at,
                    ),
                )
                inserted += int(cursor.rowcount or 0)
    return inserted


def _summary(conn: sqlite3.Connection, start_date: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS total,
               COUNT(DISTINCT trade_date) AS days,
               SUM(fresh_signal) AS fresh,
               MIN(trade_date) AS first_date,
               MAX(trade_date) AS last_date
        FROM signals
        WHERE trade_date >= ?
        """,
        (start_date,),
    ).fetchone()
    return {
        "total": int(row["total"] or 0),
        "days": int(row["days"] or 0),
        "fresh": int(row["fresh"] or 0),
        "first_date": row["first_date"],
        "last_date": row["last_date"],
    }


def recent(days: int = 30, limit: int = 200) -> dict[str, Any]:
    days = max(1, min(int(days), 3650))
    limit = max(1, min(int(limit), 2000))
    start_date = (ds.now_beijing().date() - timedelta(days=days)).isoformat()
    with _lock, closing(_connect()) as conn:
        summary = _summary(conn, start_date)
        rows = conn.execute(
            """
            SELECT trade_date, symbol, name, quality_score, grade, signal_status,
                   fresh_signal, top_rank, trend_score, recorded_at
            FROM signals
            WHERE trade_date >= ?
            ORDER BY trade_date DESC, top_rank ASC, quality_score DESC
            LIMIT ?
            """,
            (start_date, limit),
        ).fetchall()
    return {
        "ok": True,
        "days": days,
        "start_date": start_date,
        "summary": summary,
        "items": [dict(row) for row in rows],
        "path": str(LEDGER_PATH),
    }


def all_time_summary() -> dict[str, Any]:
    with _lock, closing(_connect()) as conn:
        summary = _summary(conn, "0000-00-00")
    return {"ok": True, **summary, "path": str(LEDGER_PATH)}
