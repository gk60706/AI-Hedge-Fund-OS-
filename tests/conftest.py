"""pytest 共享夹具。"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest


@pytest.fixture
def fake_daily_df() -> pd.DataFrame:
    """模拟 AkShare 日线接口返回（中文列名）。"""
    return pd.DataFrame(
        {
            "日期": ["2026-09-04", "2026-09-07"],
            "开盘": [10.0, 10.2],
            "收盘": [10.2, 10.5],
            "最高": [10.3, 10.6],
            "最低": [9.9, 10.1],
            "成交量": [1000000, 1200000],
            "成交额": [1.02e8, 1.26e8],
            "振幅": [3.9, 4.9],
            "涨跌幅": [2.0, 2.94],
            "涨跌额": [0.2, 0.3],
            "换手率": [1.1, 1.3],
        }
    )


@pytest.fixture
def fake_spot_df() -> pd.DataFrame:
    """模拟 AkShare 全市场快照（仅含目标行）。"""
    return pd.DataFrame(
        {
            "代码": ["000001"],
            "名称": ["平安银行"],
            "最新价": [10.5],
            "涨跌幅": [2.94],
            "成交量": [1200000],
            "成交额": [1.26e8],
        }
    )


@pytest.fixture
def fake_company_info_df() -> pd.DataFrame:
    """模拟 AkShare 个股信息接口返回。"""
    return pd.DataFrame({"item": ["股票简称", "行业"], "value": ["平安银行", "银行"]})


@pytest.fixture
def isolated_reports(monkeypatch, tmp_path) -> SimpleNamespace:
    """将报告输出目录隔离到临时目录，避免污染项目 reports/。"""
    from app.reports import service as report_service

    target = tmp_path / "reports"
    monkeypatch.setattr(report_service, "get_settings", lambda: SimpleNamespace(report_dir=target))
    return SimpleNamespace(dir=target)
